"""
Centralized, validated app configuration.

Import `settings` from this module instead of reading `os.environ` directly
anywhere else in the codebase. If a required variable is missing or empty,
this fails immediately on import with a clear message — not later, deep in
a stack trace when ChatOpenAI or the Langfuse handler first tries to use it.
"""

import sys

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",       # ignore unrelated env vars instead of erroring on them
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    langfuse_public_key: str = Field(..., alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(..., alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(..., alias="LANGFUSE_HOST")

    @field_validator(
        "openai_api_key", "langfuse_public_key", "langfuse_secret_key", "langfuse_host"
    )
    @classmethod
    def not_blank(cls, v: str, info) -> str:
        # Catches "var is set but set to an empty string" — a plain
        # required-field check alone won't catch that case.
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} is set but empty")
        return v


def load_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        sys.stderr.write(
            "\n[settings] Missing or invalid configuration.\n"
            "Check that your .env file exists (copy .env.example -> .env) "
            "and every required variable is filled in.\n\n"
            f"Details:\n{e}\n\n"
        )
        raise SystemExit(1)


settings = load_settings()