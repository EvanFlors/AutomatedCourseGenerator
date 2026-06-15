from typing import Protocol, TypeVar

from cogenai.agents.config import AgentConfig

Input = TypeVar("Input")
Output = TypeVar("Output")

class Agent(Protocol[Input, Output]):

    @property
    def name(self) -> str:
        ...

    @property
    def config(self) -> AgentConfig:
        ...

    def run(self, input_data: Input) -> Output:
        ...
