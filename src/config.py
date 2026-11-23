from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    tavily_api_key: str = ""
    tavily_search_depth: str = "basic"
    supabase_url: str = ""
    supabase_key: str = ""
    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    sqlite_path: str = "signaldraft.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
