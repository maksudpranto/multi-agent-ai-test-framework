from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Sensible default model per provider, so switching to a real backend only
# requires setting LLM_PROVIDER (+ the key). A model literally named after the
# mock (or left blank) is treated as "not chosen" and resolved from here.
_PROVIDER_DEFAULT_MODEL = {
    "mock": "mock-requirement-analysis",
    "gemini": "gemini-flash-latest",
    "anthropic": "claude-sonnet-4-5",
    "ollama": "llama3.1",
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-3.3-70b-instruct:free",
}

# Base URLs for OpenAI-compatible hosts (one provider class serves all).
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./app.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    default_llm_model: str = "mock-requirement-analysis"
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def effective_model(self) -> str:
        """The model name to actually send to the provider.

        If DEFAULT_LLM_MODEL is a real, provider-appropriate value the user set,
        respect it. Otherwise (blank, or still the mock placeholder while the
        provider is real) fall back to a sane default for the chosen provider —
        so "make it AI-powered" is just LLM_PROVIDER + key, no model guessing."""
        provider = self.llm_provider.lower().strip()
        chosen = (self.default_llm_model or "").strip()
        placeholder = not chosen or chosen.startswith("mock")
        if provider != "mock" and placeholder:
            return _PROVIDER_DEFAULT_MODEL.get(provider, chosen or "")
        return chosen or _PROVIDER_DEFAULT_MODEL.get(provider, "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
