from cogenai.domain.value_objects.llm import CompletionRequest, Model
from cogenai.infrastructure.llm.gemini import GeminiAdapter

model = GeminiAdapter(
    use_credentials=True,
    location="us-central1",
)

request = CompletionRequest(
    prompt="Course skeleton to learn Python.",
    model=Model(name="gemini-2.5-flash")
)

response = model.complete(request)

print(f"Response: {response.text}")
print(f"Usage: {response.usage}")
