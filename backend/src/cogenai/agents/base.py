from dataclasses import dataclass
from typing import Generic, TypeVar

from cogenai.agents.config import AgentConfig
from cogenai.bootstrap.logging import get_logger
from cogenai.domain.ports.llm import LLMProvider
from cogenai.domain.value_objects.llm import CompletionRequest
from cogenai.prompt import get_prompt as yaml_get_prompt

logger = get_logger(__name__)

Input = TypeVar("Input")
Output = TypeVar("Output")


@dataclass
class BaseAgent(Generic[Input, Output]):
    name: str
    config: AgentConfig
    llm_provider: LLMProvider

    def _get_prompt(self, version: str = "1.0.0") -> str:
        bundle = yaml_get_prompt(self.name, version)
        if bundle is None:
            raise ValueError(
                f"No YAML prompt registered for {self.name} version {version}"
            )
        return bundle.system_prompt

    def _call_llm(
        self,
        prompt: str,
        system_prompt: str = "",
    ) -> str:
        request = CompletionRequest(
            prompt=prompt,
            model=self.config.model,
            system_prompt=system_prompt or self.config.system_prompt,
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
