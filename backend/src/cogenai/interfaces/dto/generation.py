from __future__ import annotations

from pydantic import BaseModel, Field


class AgentTraceEntryDTO(BaseModel):
    agent: str = Field(default="", description="The name of the agent that produced this trace entry.")
    phase: str = Field(default="", description="The phase of the agent's work (draft, evaluate, refine, finalize).")
    iteration: int = 0
    started_at: str = ""
    completed_at: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    status: str = "success"


class RefinementDTO(BaseModel):
    iterations: int = 0
    max_iterations: int = 3
    termination_reason: str = "quality_threshold"


class TokenUsageDTO(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class GenerationMetadataDTO(BaseModel):
    job_id: str = Field(default="", description="A unique identifier for the job.")
    provider: str = Field(default="", description="The LLM provider used.")
    model: str = Field(default="", description="The model used.")
    prompt_version: str = "1.0.0"
    rubric_version: str = "1.0.0"
    started_at: str = ""
    completed_at: str = ""
    tokens: TokenUsageDTO = Field(default_factory=TokenUsageDTO)
    agent_trace: list[AgentTraceEntryDTO] = Field(default_factory=list)
    refinement: RefinementDTO = Field(default_factory=RefinementDTO)