"""
ReAct Agent with Anthropic Native Tool Calling

Upgraded from text-based tool parsing to use Anthropic's tool_use/tool_result blocks.
Operates on vault data (5 tools) and Python projects (7 tools) as its action space.
"""

import json
import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from anthropic import Anthropic, RateLimitError
from dotenv import load_dotenv

from ..vault import VaultTools, Config
from ..projects import ProjectTools


# Load environment variables
load_dotenv()


# Pricing per 1M tokens (as of 2025)
# Source: https://www.anthropic.com/pricing
PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
}


@dataclass
class TokenUsage:
    """Track token usage and costs for a single API call."""
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def cost(self) -> float:
        """Calculate cost in USD."""
        if self.model not in PRICING:
            return 0.0
        pricing = PRICING[self.model]
        input_cost = (self.input_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.output_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost


@dataclass
class Step:
    """Single step in the ReAct loop (now tool-based)."""
    step_number: int
    thought: str  # Text blocks before tool_use
    action: str  # Tool name
    action_input: Dict[str, Any]  # Tool input
    observation: str  # Tool output
    token_usage: Optional[TokenUsage] = None


@dataclass
class ReActResult:
    """Final result of ReAct loop execution."""
    task: str
    completed: bool
    steps: List[Step]
    final_answer: Optional[str]
    finding_path: Optional[str]
    total_steps: int
    total_tokens: int
    total_cost: float
    reason: str  # 'completed', 'max_steps_reached', 'too_many_errors', 'error: ...'


# Tool schemas for Anthropic API
VAULT_TOOLS = [
    {
        "name": "vault__read_file",
        "description": "Read a file from the Obsidian vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from vault root (e.g., '06-findings/foo.md')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "vault__write_file",
        "description": "Create or overwrite a file in the vault. Only accepts markdown files.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from vault root"
                },
                "content": {
                    "type": "string",
                    "description": "File content to write"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "vault__append_file",
        "description": "Append content to an existing file in the vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path from vault root"
                },
                "content": {
                    "type": "string",
                    "description": "Content to append"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "vault__list_files",
        "description": "List files in the vault matching a glob pattern",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '**/*.md', '06-findings/*'). Omit for all files."
                }
            },
            "required": []
        }
    },
    {
        "name": "vault__search_content",
        "description": "Search file contents in the vault using regex patterns",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search pattern (regex supported, case-insensitive)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to limit search scope"
                }
            },
            "required": ["query"]
        }
    }
]

PROJECTS_TOOLS = [
    {
        "name": "projects__create_structure",
        "description": "Scaffold a complete Python project with Poetry, pytest, and GitHub-ready structure",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug matching ^[a-z0-9-]+$ (e.g., 'meeting-summarizer')",
                    "pattern": "^[a-z0-9-]+$"
                }
            },
            "required": ["slug"]
        }
    },
    {
        "name": "projects__write_file",
        "description": "Write any file type (.py, .toml, .yml, etc.) into the project directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                },
                "path": {
                    "type": "string",
                    "description": "Relative path within project (e.g., 'src/foo/main.py')"
                },
                "content": {
                    "type": "string",
                    "description": "File content"
                }
            },
            "required": ["slug", "path", "content"]
        }
    },
    {
        "name": "projects__read_file",
        "description": "Read a file from the project directory",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                },
                "path": {
                    "type": "string",
                    "description": "Relative path within project"
                }
            },
            "required": ["slug", "path"]
        }
    },
    {
        "name": "projects__list_files",
        "description": "List files in the project directory with optional glob pattern",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                },
                "pattern": {
                    "type": "string",
                    "description": "Optional glob pattern (e.g., '**/*.py', 'src/*')"
                }
            },
            "required": ["slug"]
        }
    },
    {
        "name": "projects__check_syntax",
        "description": "Compile Python file to check for syntax errors without executing",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                },
                "path": {
                    "type": "string",
                    "description": "Relative path to Python file (e.g., 'src/foo/main.py')"
                }
            },
            "required": ["slug", "path"]
        }
    },
    {
        "name": "projects__check_dependencies",
        "description": "Run poetry check to verify dependency tree and pyproject.toml validity",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                }
            },
            "required": ["slug"]
        }
    },
    {
        "name": "projects__run_tests",
        "description": "Execute poetry run pytest in project. Auto-installs dependencies if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds (default 60)"
                }
            },
            "required": ["slug"]
        }
    }
]


class ReactAgent:
    """
    ReAct agent using Anthropic's native tool calling.

    Architecture:
    - Defines 12 tools (5 vault + 7 projects) as Anthropic tool schemas
    - Uses tool_use/tool_result message format (no text parsing)
    - Tool registry maps tool names to callable methods
    - Structured logging of tool calls and results

    Action space (12 tools):
    1-5. vault__* tools for Obsidian vault operations
    6-12. projects__* tools for Python project code generation
    """

    def __init__(
        self,
        api_key: str,
        vault: VaultTools,
        projects: ProjectTools,
        model: str = "claude-sonnet-4-20250514",
        max_steps: int = 20,
        verbose: bool = True,
        preloaded_firm_context: str = "",
        skill_content: str = "",
        retry_max_attempts: int = 5,
        retry_initial_delay: float = 1.0,
    ):
        """
        Initialize ReactAgent with native tool calling.

        Args:
            api_key: Anthropic API key
            vault: VaultTools instance for vault operations
            projects: ProjectTools instance for code project operations
            model: Claude model to use
            max_steps: Maximum ReAct loop iterations
            verbose: Enable detailed logging
            preloaded_firm_context: Firm context pre-loaded into system prompt
            skill_content: Skill file content for role-specific behavior
            retry_max_attempts: Max retry attempts for rate limits
            retry_initial_delay: Initial retry delay in seconds
        """
        self.client = Anthropic(api_key=api_key)
        self.vault = vault
        self.projects = projects
        self.model = model
        self.max_steps = max_steps
        self.verbose = verbose
        self.retry_max_attempts = retry_max_attempts
        self.retry_initial_delay = retry_initial_delay

        # Token tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Tool registry: maps tool names to callables
        self.tool_registry = {
            # Vault tools
            "vault__read_file": self.vault.read_file,
            "vault__write_file": self.vault.write_file,
            "vault__append_file": self.vault.append_file,
            "vault__list_files": self.vault.list_files,
            "vault__search_content": self.vault.search_content,
            # Projects tools
            "projects__create_structure": self.projects.create_structure,
            "projects__write_file": self.projects.write_file,
            "projects__read_file": self.projects.read_file,
            "projects__list_files": self.projects.list_files,
            "projects__check_syntax": self.projects.check_syntax,
            "projects__check_dependencies": self.projects.check_dependencies,
            "projects__run_tests": self.projects.run_tests,
        }

        # Build system prompt (Anthropic provides tool docs)
        self.system_prompt = self._build_system_prompt(
            preloaded_firm_context,
            skill_content
        )

        # All tools available to this agent
        self.tools = VAULT_TOOLS + PROJECTS_TOOLS

    def _build_system_prompt(self, firm_context: str, skill: str) -> str:
        """Build system prompt without tool documentation (Anthropic provides it)."""
        return f"""You are a specialized AI agent with access to vault and project tools.

{firm_context}

{skill}

You have access to 12 tools total:
- 5 vault tools for reading/writing markdown documentation
- 7 projects tools for creating and managing Python code projects

Use vault tools for documentation. Use projects tools for code.

Work step by step, using tools as needed to complete your task."""

    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool from the registry.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters as dict

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or execution fails
        """
        if tool_name not in self.tool_registry:
            raise ValueError(f"Unknown tool: {tool_name}")

        try:
            callable_func = self.tool_registry[tool_name]

            # Call the function with unpacked kwargs
            return callable_func(**tool_input)

        except Exception as e:
            raise ValueError(f"Tool execution error: {str(e)}")

    def _call_api_with_retry(self, **kwargs) -> Any:
        """
        Call Anthropic API with exponential backoff retry logic for rate limits.

        Args:
            **kwargs: Arguments to pass to client.messages.create()

        Returns:
            API response

        Raises:
            RateLimitError: If max retry attempts exceeded
        """
        delay = self.retry_initial_delay
        last_error = None

        for attempt in range(1, self.retry_max_attempts + 1):
            try:
                return self.client.messages.create(**kwargs)

            except RateLimitError as e:
                last_error = e

                if attempt == self.retry_max_attempts:
                    # Max attempts reached
                    if self.verbose:
                        print(f"\n⚠️  Rate limit error after {attempt} attempts. Max retries exceeded.")
                    raise

                # Exponential backoff
                if self.verbose:
                    print(f"\n⏳ Rate limited. Retry {attempt}/{self.retry_max_attempts} in {delay:.1f}s...")

                time.sleep(delay)
                delay *= 2  # Exponential backoff

            except Exception as e:
                # Non-rate-limit errors: don't retry, raise immediately
                raise

        # Should never reach here, but just in case
        raise last_error

    def _log_step(self, step: Step) -> None:
        """Log a completed step to console."""
        if not self.verbose:
            return

        print(f"\n{'='*80}")
        print(f"STEP {step.step_number}")
        print(f"{'='*80}\n")

        if step.thought:
            print(f"💭 THOUGHT:\n{step.thought}\n")

        print(f"🎯 ACTION: {step.action}")
        print(f"📋 INPUT: {json.dumps(step.action_input, indent=2)}\n")

        print(f"👁️  OBSERVATION:\n{step.observation}\n")

        if step.token_usage:
            print(f"💰 Tokens: {step.token_usage.input_tokens:,} in / {step.token_usage.output_tokens:,} out | Cost: ${step.token_usage.cost:.6f}\n")

    def _generate_finding(self, task: str, steps: List[Step], final_answer: str) -> str:
        """Generate a finding document and write to vault."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.now().strftime("%Y-%m-%d")

        # Build markdown content
        content = f"""---
type: finding
created: {date_str}
updated: {date_str}
tags: [react-agent, automated-finding]
generated-by: ReactAgent
session: {date_str}
confidence: high
source: agent research
verified: false
---

# ReAct Agent Finding: {task[:100]}

**Task**: {task}
**Completed**: {timestamp}
**Total Steps**: {len(steps)}

---

## Executive Summary

{final_answer}

---

## Reasoning Trace

"""

        for step in steps:
            content += f"**Step {step.step_number}**: {step.thought if step.thought else f'Using tool: {step.action}'}\n"
            content += f"- Action: `{step.action}`\n"
            content += f"- Result: {step.observation[:200]}{'...' if len(step.observation) > 200 else ''}\n\n"

        content += """
---

## Metadata

- **Agent**: ReactAgent
- **Model**: """ + self.model + f"""
- **Steps Taken**: {len(steps)}
- **Max Steps**: {self.max_steps}

"""

        # Write to vault
        filepath = f"06-findings/{date_str}-react-{task[:30].replace(' ', '-').lower()}.md"
        self.vault.write_file(filepath, content)

        return filepath

    def run(self, task: str) -> ReActResult:
        """
        Execute the ReAct loop using native tool calling.

        Process:
        1. Send task with tools available
        2. Loop (max max_steps):
           a. If assistant returns text: record as thought
           b. If assistant returns tool_use: execute tool
           c. Send tool_result back
           d. If assistant provides final answer: complete
        3. Generate finding document
        4. Return result
        """
        if self.verbose:
            print("\n" + "="*80)
            print("🤖 REACT AGENT STARTING (Native Tool Calling)")
            print("="*80)
            print(f"\n📋 TASK: {task}\n")
            print(f"🔧 MODEL: {self.model}")
            print(f"🛠️  TOOLS: {len(self.tools)} available")
            print(f"📊 MAX STEPS: {self.max_steps}\n")

        steps: List[Step] = []
        consecutive_errors = 0

        # Message history for Anthropic API
        messages = [{
            "role": "user",
            "content": task
        }]

        for step_num in range(1, self.max_steps + 1):
            try:
                # Call API with tools
                response = self._call_api_with_retry(
                    model=self.model,
                    max_tokens=4096,
                    system=self.system_prompt,
                    messages=messages,
                    tools=self.tools  # Native tool support
                )

                # Track token usage
                usage = TokenUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    model=self.model
                )
                self.total_input_tokens += usage.input_tokens
                self.total_output_tokens += usage.output_tokens

                # Process response content blocks
                assistant_content = []
                tool_results = []
                text_blocks = []
                has_tool_use = False

                for block in response.content:
                    if block.type == "text":
                        # Text block: could be reasoning or final answer
                        text = block.text
                        text_blocks.append(text)
                        assistant_content.append(block)

                        if self.verbose:
                            print(f"\n💭 ASSISTANT:\n{text}\n")

                    elif block.type == "tool_use":
                        has_tool_use = True
                        # Tool use block: execute the tool
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        assistant_content.append(block)

                        if self.verbose:
                            print(f"\n🔧 TOOL CALL: {tool_name}")
                            print(f"📥 INPUT: {json.dumps(tool_input, indent=2)}\n")

                        # Execute tool
                        try:
                            result = self._execute_tool(tool_name, tool_input)

                            # Format result as string for observation
                            if isinstance(result, (list, dict)):
                                observation = json.dumps(result, indent=2)
                            else:
                                observation = str(result)

                            is_error = False
                            consecutive_errors = 0

                            if self.verbose:
                                print(f"✅ RESULT:\n{observation[:500]}{'...' if len(observation) > 500 else ''}\n")

                        except Exception as e:
                            observation = f"Error: {str(e)}"
                            is_error = True
                            consecutive_errors += 1

                            if self.verbose:
                                print(f"❌ ERROR:\n{observation}\n")

                        # Create tool result for next message
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": observation,
                            "is_error": is_error
                        })

                        # Record step (thought is any text before this tool_use)
                        thought = "\n".join(text_blocks) if text_blocks else f"Using tool: {tool_name}"
                        step = Step(
                            step_number=step_num,
                            thought=thought,
                            action=tool_name,
                            action_input=tool_input,
                            observation=observation,
                            token_usage=usage
                        )
                        steps.append(step)

                        if self.verbose:
                            self._log_step(step)

                        # Clear text blocks for next tool
                        text_blocks = []

                # Check for task completion (end_turn AND no tool_use in response)
                if response.stop_reason == "end_turn" and not has_tool_use:
                    # Model decided it's done
                    final_answer = "\n".join(text_blocks) if text_blocks else "Task complete"

                    total_cost = sum(s.token_usage.cost for s in steps if s.token_usage) + usage.cost

                    if self.verbose:
                        print(f"\n{'='*80}")
                        print(f"✅ TASK COMPLETED (Step {step_num})")
                        print(f"{'='*80}")
                        print(f"\n🎯 FINAL ANSWER:\n{final_answer}\n")
                        print(f"💵 TOTAL COST: ${total_cost:.6f}")

                    finding_path = self._generate_finding(task, steps, final_answer)

                    return ReActResult(
                        task=task,
                        completed=True,
                        steps=steps,
                        final_answer=final_answer,
                        finding_path=finding_path,
                        total_steps=step_num,
                        total_tokens=self.total_input_tokens + self.total_output_tokens,
                        total_cost=total_cost,
                        reason="completed"
                    )

                # Add assistant message to history
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })

                # If we have tool results, send them back
                if tool_results:
                    messages.append({
                        "role": "user",
                        "content": tool_results
                    })

                # Check for too many consecutive errors
                if consecutive_errors >= 3:
                    return ReActResult(
                        task=task,
                        completed=False,
                        steps=steps,
                        final_answer=None,
                        finding_path=None,
                        total_steps=step_num,
                        total_tokens=self.total_input_tokens + self.total_output_tokens,
                        total_cost=sum(s.token_usage.cost for s in steps if s.token_usage),
                        reason="too_many_errors"
                    )

            except Exception as e:
                if self.verbose:
                    print(f"\n❌ Error in step {step_num}: {str(e)}\n")

                return ReActResult(
                    task=task,
                    completed=False,
                    steps=steps,
                    final_answer=None,
                    finding_path=None,
                    total_steps=step_num,
                    total_tokens=self.total_input_tokens + self.total_output_tokens,
                    total_cost=sum(s.token_usage.cost for s in steps if s.token_usage),
                    reason=f"error: {str(e)}"
                )

        # Max steps reached
        return ReActResult(
            task=task,
            completed=False,
            steps=steps,
            final_answer=None,
            finding_path=None,
            total_steps=self.max_steps,
            total_tokens=self.total_input_tokens + self.total_output_tokens,
            total_cost=sum(s.token_usage.cost for s in steps if s.token_usage),
            reason="max_steps_reached"
        )
