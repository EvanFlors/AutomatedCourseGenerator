from dataclasses import dataclass, field


@dataclass
class PromptRegistry:

    _prompts: dict[str, dict[str, str]] = field(default_factory=dict)

    def register(self, agent_name: str, version: str, prompt: str) -> None:
        if agent_name not in self._prompts:
            self._prompts[agent_name] = {}
        self._prompts[agent_name][version] = prompt

    def get_prompt(self, agent_name: str, version: str) -> str | None:
        return self._prompts.get(agent_name, {}).get(version, None)

    def has_prompt(self, agent_name: str, version: str) -> bool:
        return self.get_prompt(agent_name, version) is not None

prompt_registry = PromptRegistry()
