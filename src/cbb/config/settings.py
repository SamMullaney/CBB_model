from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    odds_api_key: str = ""
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    discord_webhook_url: str = ""


settings = Settings()
