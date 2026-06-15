from cogenai.agents.config import AgentConfig
from cogenai.agents_implementations.context_synthesizer import (
    ContextSynthesizerAgent,
    ContextSynthesizerInput,
)
from cogenai.infrastructure.llm.gemini import GeminiAdapter

model = GeminiAdapter(
    use_credentials=True,
    location="us-central1",
    scope="https://www.googleapis.com/auth/cloud-platform"
)

config = AgentConfig.default()

agent = ContextSynthesizerAgent(
    config=config,
    llm_provider=model
)

agent_input = ContextSynthesizerInput(
    topic="Python for Data Science",
    audience="beginners",
    difficulty="beginner",
    learning_outcomes=("Learn Python basics", "Analyze data with pandas", "Create visualizations"),
    text_instructions="Create a beginner-friendly course on data science with Python.",
    documents=("pandas docs", "matplotlib docs"),
    reference_courses=("CS50", "Intro to Python"),
    domain_knowledge=("Python", "Data Analysis", "Statistics")
)

context = agent.run(agent_input)
