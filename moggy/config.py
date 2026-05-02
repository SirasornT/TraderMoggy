from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_FIELDS = {"anthropic_api_key", "reddit_client_id", "reddit_client_secret"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    reddit_client_id: str = Field(default="", validation_alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", validation_alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="MoggyTrader/0.1", validation_alias="REDDIT_USER_AGENT")
    default_model: str = Field(default="claude-sonnet-4-6", validation_alias="DEFAULT_MODEL")
    discover_limit: int = Field(default=15, validation_alias="DISCOVER_LIMIT")
    discover_min_score: float = Field(default=0.0, validation_alias="DISCOVER_MIN_SCORE")
    output_dir: str = Field(default="./output", validation_alias="OUTPUT_DIR")

    def display(self) -> dict[str, str | int | float]:
        result: dict[str, str | int | float] = {}
        for field_name in Settings.model_fields:
            value = getattr(self, field_name)
            if field_name in _SECRET_FIELDS and value:
                result[field_name] = "***"
            else:
                result[field_name] = value
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
