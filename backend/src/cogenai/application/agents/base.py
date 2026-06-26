from dataclasses import dataclass
from typing import Generic, TypeVar

from cogenai.application.agents.config import AgentConfig
from cogenai.shared.logging import get_logger
from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import CompletionRequest
from cogenai.prompt import (
    PromptBundle,
    get_prompt as yaml_get_prompt,
    render_schema_instruction,
)

logger = get_logger(__name__)

Input = TypeVar("Input")
Output = TypeVar("Output")


@dataclass
class BaseAgent(Generic[Input, Output]):
    name: str
    config: AgentConfig
    llm_provider: LLMProvider

    def _get_prompt_bundle(self, version: str = "1.0.0") -> PromptBundle:
        """Return the full PromptBundle (system_prompt + optional schema)."""
        bundle = yaml_get_prompt(self.name, version)
        if bundle is None:
            raise ValueError(
                f"No YAML prompt registered for {self.name} version {version}"
            )
        return bundle

    def _get_prompt(self, version: str = "1.0.0") -> str:
        """Return just the system_prompt string (back-compat shim)."""
        return self._get_prompt_bundle(version).system_prompt

    def _build_system_prompt(
        self,
        system_prompt: str,
        bundle: PromptBundle | None = None,
    ) -> str:
        """Compose the final system prompt, appending a schema directive if present.

        If `bundle` carries a `schema` mapping, it is rendered as an
        OUTPUT SCHEMA suffix so providers that don't support native
        `response_schema` still get a strong prompt to emit conforming JSON.
        """
        base = system_prompt or self.config.system_prompt
        if bundle is None or bundle.schema is None:
            return base
        return base + render_schema_instruction(bundle.schema)

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
        bundle: PromptBundle | None = None,
    ) -> str:
        final_system = self._build_system_prompt(system_prompt, bundle)
        request = CompletionRequest(
            prompt=prompt,
            model=self.config.model_for(self.name),
            system_prompt=final_system,
            output_schema=bundle.schema if bundle else None,
        )
        response = self.llm_provider.complete(request)
        return response.text

    def _log_execution(self, input_data: Input, output: Output) -> None:
        logger.info(
            "agent_executed",
            agent=self.name,
            input_type=type(input_data).__name__,
            output_type=type(output).__name__,
        )