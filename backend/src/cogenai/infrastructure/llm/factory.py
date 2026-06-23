from functools import cache


class LLMClientFactory:

    @staticmethod
    @cache
    def gemini(
        api_key: str | None = None,
        *,  # Keyword-Only Parameters (must be specified using keywords)
        use_credentials: bool = False,
        location: str | None = None,
    ):
        try:
            from google import genai
            from google.auth import default
        except ImportError as exc:
            raise ImportError(
                "Install google-genai and google-auth: pip install google-genai google-auth"
            ) from exc

        if not use_credentials:
            return genai.Client(api_key=api_key)

        credentials, project_id = default()

        return genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            credentials=credentials,
        )
