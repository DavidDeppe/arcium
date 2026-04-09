"""
Backend abstraction layer for agent execution.

Provides a common interface for executing agent tasks via different backends:
- AnthropicBackend: Direct API calls to Anthropic (ReactAgent multi-turn loop)
- ClaudeCodeAgent: Subprocess calls to Claude Code CLI (autonomous single-shot execution)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class AgentResult:
    """
    Normalized result from any agent execution backend.

    Common interface whether from ReactAgent (multi-turn loop) or ClaudeCodeAgent
    (single subprocess call).
    """
    success: bool
    result: str  # Final answer/output text
    total_cost: float
    total_tokens: int
    total_steps: int
    error: Optional[str] = None
    metadata: Dict[str, Any] = None  # Backend-specific data

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseAgentBackend(ABC):
    """
    Abstract base class for agent execution backends.

    Defines the interface that all backends must implement to execute agent tasks.
    """

    @abstractmethod
    def execute(
        self,
        task: str,
        system_prompt: str,
        role: str = "agent",
        iteration: int = 1,
        **kwargs
    ) -> AgentResult:
        """
        Execute an agent task.

        Args:
            task: The task description/prompt to execute
            system_prompt: System prompt to configure agent behavior
            role: Agent role name (for logging/debugging)
            iteration: Iteration number in pipeline (for logging)
            **kwargs: Backend-specific additional arguments

        Returns:
            AgentResult with normalized response

        Raises:
            May raise backend-specific exceptions
        """
        pass


class AnthropicBackend(BaseAgentBackend):
    """
    Backend that executes tasks via ReactAgent with Anthropic API.

    Uses multi-turn conversation loop with explicit tool orchestration.
    Suitable for research/planning tasks (Team Lead, Architect, Communications).
    """

    def __init__(
        self,
        react_agent,  # ReactAgent instance (avoid circular import)
    ):
        """
        Initialize AnthropicBackend.

        Args:
            react_agent: Configured ReactAgent instance
        """
        self.react_agent = react_agent

    def execute(
        self,
        task: str,
        system_prompt: str = None,  # Ignored - ReactAgent uses pre-configured system prompt
        role: str = "agent",
        iteration: int = 1,
        **kwargs
    ) -> AgentResult:
        """
        Execute task via ReactAgent multi-turn loop.

        Args:
            task: Task to execute
            system_prompt: Ignored (ReactAgent has pre-configured system prompt with skills)
            role: Agent role (for logging)
            iteration: Iteration number (unused here, ReactAgent doesn't track iterations)
            **kwargs: Additional args (unused)

        Returns:
            AgentResult with ReactAgent execution results

        Raises:
            Any exceptions from ReactAgent.run()
        """
        # Run ReactAgent
        result = self.react_agent.run(task)

        # Convert ReactAgent.ReActResult to AgentResult
        return AgentResult(
            success=result.completed,
            result=result.final_answer or "Task did not complete",
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            total_steps=result.total_steps,
            error=None if result.completed else result.reason,
            metadata={
                "backend": "anthropic",
                "model": self.react_agent.model,
                "finding_path": result.finding_path,
                "steps": [
                    {
                        "step_number": s.step_number,
                        "action": s.action,
                        "observation": s.observation[:200] + "..." if len(s.observation) > 200 else s.observation
                    }
                    for s in result.steps
                ]
            }
        )
