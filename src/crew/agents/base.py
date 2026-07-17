"""
Base agent class for all research agents.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from src.config import get_model_for_agent
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AgentContext(BaseModel):
    """Context passed to agents during execution."""
    question: str
    trace_id: str = ""
    run_id: str = ""
    iteration: int = 0
    model_override: str | None = None
    temperature: float = 0.3
    max_tokens: int = 4000


class BaseAgent(ABC):
    """Abstract base class for all research agents."""

    def __init__(
        self,
        role: str,
        goal: str,
        backstory: str,
        tools: list[Any] | None = None,
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        verbose: bool = False,
    ):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.model = model or get_model_for_agent(role)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose

    def get_system_prompt(self, context: AgentContext | None = None) -> str:
        """Build the system prompt for this agent."""
        lines = [
            f"You are {self.role}.",
            "",
            self.backstory,
            "",
            f"Your goal: {self.goal}",
            "",
            "Guidelines:",
            "- Always respond with valid structured output",
            "- Use your available tools when needed",
            "- If you cannot find information, state that clearly",
            "- Be precise and cite your sources",
            "- Maintain a professional, academic tone",
        ]

        if context:
            if context.iteration > 0:
                lines.append(f"- This is revision iteration {context.iteration}")

        return "\n".join(lines)

    def get_tool_descriptions(self) -> list[str]:
        """Get descriptions of available tools."""
        return [t.__doc__ or t.__class__.__name__ for t in self.tools]

    def _llm_completion(
        self,
        messages: list[dict],
        context: AgentContext | None = None,
        response_format: dict | None = None,
    ) -> tuple[str, dict]:
        """Call the LLM via litellm.completion().

        Returns:
            Tuple of (response_content, usage_dict).
            usage_dict has keys: prompt_tokens, completion_tokens.
        """
        import litellm
        temperature = context.temperature if context else self.temperature
        max_tokens = context.max_tokens if context else self.max_tokens
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response_format:
            kwargs["response_format"] = response_format

        response = litellm.completion(**kwargs)
        content = response.choices[0].message.content
        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0)
                          or getattr(response.usage, "input_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0)
                             or getattr(response.usage, "output_tokens", 0),
        }
        self._last_usage = usage
        return content or "", usage

    @abstractmethod
    def execute(self, context: AgentContext, **kwargs) -> Any:
        """Execute the agent's task."""
        pass


class CrewAIAgentWrapper:
    """Wraps a BaseAgent for use with CrewAI."""

    def __init__(self, agent: BaseAgent):
        self.agent = agent
        self.role = agent.role
        self.goal = agent.goal
        self.backstory = agent.backstory

    def to_crewai_agent(self, allow_delegation: bool = False, max_iter: int = 15):
        """Convert to CrewAI Agent."""
        try:
            from crewai import Agent as CrewAgent
            return CrewAgent(
                role=self.role,
                goal=self.goal,
                backstory=self.backstory,
                tools=self.agent.tools[:4] if hasattr(self.agent, 'tools') else [],
                allow_delegation=allow_delegation,
                verbose=self.agent.verbose if hasattr(self.agent, 'verbose') else False,
                max_iter=max_iter,
            )
        except Exception as e:
            logger.error(f"Could not create CrewAI Agent: {e}")
            return None
