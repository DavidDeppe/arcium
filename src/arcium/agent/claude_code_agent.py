"""
arcium/agent/claude_code_agent.py

Autonomous agent that executes tasks by delegating to Claude Code CLI in headless mode.

Unlike ReactAgent (multi-turn loop with explicit tool orchestration), ClaudeCodeAgent
makes ONE subprocess call and Claude Code handles the entire conversation internally
including all tool executions.

This is ideal for code generation tasks (Engineer, Critic roles) where:
- Claude Code's native file editing is superior to API-based text replacement
- No Anthropic API rate limits interfere with lengthy code generation sessions
- Built-in tool approval system provides safety guardrails
"""

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass
class ClaudeCodeResult:
    """Normalized result from Claude Code execution."""
    success: bool
    result: str  # Final text output from Claude Code
    session_id: str
    total_cost_usd: float
    usage: Dict[str, Any]  # Token usage stats
    raw_stdout: str  # Full stdout for debugging/logging
    error: Optional[str] = None


class ClaudeCodeAgent:
    """
    Executes tasks via Claude Code CLI in headless mode with MCP tool access.

    Security Note:
    Uses --dangerously-skip-permissions flag for pipeline automation. This is
    intentional - MCP server provides security boundaries by constraining tool
    access to vault and projects directories. For production deployments, run
    this inside Docker containers for additional isolation.

    See vault finding: 06-findings/claude-code-headless-security.md
    """

    def __init__(
        self,
        mcp_config_path: Optional[str] = None,
        vault_path: Optional[str] = None,
        projects_path: Optional[str] = None,
        reasoning_log_dir: Optional[str] = None,
    ):
        """
        Initialize ClaudeCodeAgent.

        Args:
            mcp_config_path: Path to .mcp.json config file
            vault_path: Path to Obsidian vault root
            projects_path: Path to projects directory
            reasoning_log_dir: Directory to write reasoning logs (defaults to vault/06-findings/)
        """
        # Load from environment with sensible defaults
        self.mcp_config_path = mcp_config_path or os.getenv(
            'ARCIUM_MCP_CONFIG',
            str(Path.cwd() / '.mcp.json')
        )

        self.vault_path = vault_path or os.getenv(
            'ARCIUM_VAULT_PATH',
            str(Path.home() / 'Documents' / 'arcium-vault')
        )

        self.projects_path = projects_path or os.getenv(
            'ARCIUM_PROJECTS_PATH',
            str(Path.home() / 'projects')
        )

        # Reasoning logs go to vault findings by default
        self.reasoning_log_dir = reasoning_log_dir or os.getenv(
            'ARCIUM_REASONING_LOG_DIR',
            str(Path(self.vault_path) / '06-findings')
        )

        # Validate paths
        if not Path(self.mcp_config_path).exists():
            raise FileNotFoundError(f"MCP config not found: {self.mcp_config_path}")

        Path(self.reasoning_log_dir).mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        task: str,
        system_prompt: str,
        role: str = "agent",
        poc_slug: Optional[str] = None,
        iteration: int = 1,
        timeout: int = 3600,  # 1 hour default
    ) -> ClaudeCodeResult:
        """
        Execute a task via Claude Code CLI.

        Note: Callers should prefer execute_safe() unless they specifically need
        raw exceptions for error handling.

        Args:
            task: The task description/prompt to send to Claude Code
            system_prompt: System prompt to configure Claude Code behavior
            role: Agent role name (for logging)
            poc_slug: PoC project slug (for organizing reasoning logs)
            iteration: Iteration number in pipeline (for log filename)
            timeout: Maximum execution time in seconds

        Returns:
            ClaudeCodeResult with normalized response

        Raises:
            subprocess.TimeoutExpired: If execution exceeds timeout
            subprocess.CalledProcessError: If claude CLI returns non-zero exit code
            json.JSONDecodeError: If response is not valid JSON
            RuntimeError: If response contains is_error=true
        """
        # Build command
        # NOTE: --mcp-config MUST use equals sign syntax: --mcp-config=<path>
        cmd = [
            'claude',
            '--print',
            '--output-format', 'json',
            f'--mcp-config={self.mcp_config_path}',
            '--system-prompt', system_prompt,
            '--dangerously-skip-permissions',  # Intentional - see class docstring
            task
        ]

        # Build clean environment: strip ANTHROPIC_API_KEY so claude --print
        # authenticates via Claude Code subscription (Max plan) instead of API account.
        env = {k: v for k, v in os.environ.items() if k != 'ANTHROPIC_API_KEY'}

        # Execute subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,  # Raises CalledProcessError on non-zero exit
            env=env
        )

        raw_stdout = result.stdout

        # Parse JSON response BEFORE saving log so we can detect errors
        # Expected structure: {type, subtype, result, session_id, total_cost_usd, usage, is_error}
        response = json.loads(raw_stdout)

        # Check for API-level errors (e.g., "Credit balance is too low")
        # Claude Code returns exit code 0 but sets is_error=true in JSON
        if response.get('is_error', False):
            error_message = response.get('result', 'Unknown error')
            # Save reasoning log even on failure for debugging
            if poc_slug:
                self._save_reasoning_log(raw_stdout, role, poc_slug, iteration)
            raise RuntimeError(f"Claude Code API error: {error_message}")

        # Save reasoning log on success
        if poc_slug:
            self._save_reasoning_log(raw_stdout, role, poc_slug, iteration)

        return ClaudeCodeResult(
            success=True,
            result=response.get('result', ''),
            session_id=response.get('session_id', 'unknown'),
            total_cost_usd=response.get('total_cost_usd', 0.0),
            usage=response.get('usage', {}),
            raw_stdout=raw_stdout,
            error=None
        )

    def _save_reasoning_log(
        self,
        stdout: str,
        role: str,
        poc_slug: str,
        iteration: int
    ) -> None:
        """
        Save raw Claude Code output to reasoning log file.

        Args:
            stdout: Raw stdout from claude CLI
            role: Agent role name
            poc_slug: PoC project slug
            iteration: Iteration number
        """
        # Create PoC-specific findings directory
        poc_findings_dir = Path(self.reasoning_log_dir) / f'poc-pipeline-{poc_slug}'
        poc_findings_dir.mkdir(parents=True, exist_ok=True)

        # Write log file with iteration and timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = poc_findings_dir / f'{role}-reasoning-iter{iteration}-{timestamp}.log'

        log_file.write_text(stdout)

    def execute_safe(
        self,
        task: str,
        system_prompt: str,
        role: str = "agent",
        poc_slug: Optional[str] = None,
        iteration: int = 1,
        timeout: int = 3600,
    ) -> ClaudeCodeResult:
        """
        Execute with exception handling - returns ClaudeCodeResult with error field set.

        Same args as execute(), but catches exceptions and returns them in result.
        """
        try:
            return self.execute(task, system_prompt, role, poc_slug, iteration, timeout)
        except subprocess.TimeoutExpired as e:
            # Save partial output even on timeout
            if poc_slug and e.stdout:
                try:
                    self._save_reasoning_log(e.stdout, role, poc_slug, iteration)
                except Exception:
                    pass  # Don't fail if log write fails
            return ClaudeCodeResult(
                success=False,
                result='',
                session_id='timeout',
                total_cost_usd=0.0,
                usage={},
                raw_stdout=e.stdout or '',
                error=f'Execution timed out after {timeout}s'
            )
        except subprocess.CalledProcessError as e:
            # Save stderr/stdout even on process failure
            if poc_slug and (e.stdout or e.stderr):
                try:
                    log_content = f"STDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}"
                    self._save_reasoning_log(log_content, role, poc_slug, iteration)
                except Exception:
                    pass  # Don't fail if log write fails
            return ClaudeCodeResult(
                success=False,
                result='',
                session_id='error',
                total_cost_usd=0.0,
                usage={},
                raw_stdout=e.stdout or '',
                error=f'Claude CLI returned exit code {e.returncode}: {e.stderr}'
            )
        except RuntimeError as e:
            # API-level error (e.g., "Credit balance is too low")
            # Log was already saved in execute() before raising
            return ClaudeCodeResult(
                success=False,
                result='',
                session_id='api_error',
                total_cost_usd=0.0,
                usage={},
                raw_stdout='',
                error=str(e)
            )
        except json.JSONDecodeError as e:
            # Try to save raw stdout for debugging
            if poc_slug:
                try:
                    self._save_reasoning_log(f"JSON Parse Error: {e}\n\nRaw Output:\n{result.stdout if 'result' in locals() else 'N/A'}", role, poc_slug, iteration)
                except Exception:
                    pass
            return ClaudeCodeResult(
                success=False,
                result='',
                session_id='parse_error',
                total_cost_usd=0.0,
                usage={},
                raw_stdout='',
                error=f'Failed to parse JSON response: {e}'
            )
        except Exception as e:
            return ClaudeCodeResult(
                success=False,
                result='',
                session_id='unknown_error',
                total_cost_usd=0.0,
                usage={},
                raw_stdout='',
                error=f'Unexpected error: {type(e).__name__}: {e}'
            )
