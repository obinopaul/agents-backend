from pydantic_settings import BaseSettings


class LLMConfig(BaseSettings):
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"  # Accept any model string

