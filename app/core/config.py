from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "development"
    port: int = 8000

    database_url: str

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: str = "http://localhost:5173,http://localhost:3000,https://oralcollector.shemaywam.com,https://tripod-console.shemaywam.com,https://translationhelper.shemaywam.com,https://annotationstudio.shemaywam.com,https://soundnecklace.shemaywam.com"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None

    google_api_key: str = ""
    google_maps_api_key: str = ""
    recaptcha_secret_key: str = ""
    google_embedding_model: str = "gemini-embedding-001"
    google_llm_model: str = "gemini-3.1-pro-preview"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5

    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v2"
    elevenlabs_output_format: str = "mp3_44100_128"

    ph_elevenlabs_api_key: str = ""

    gcs_bucket_name: str = ""
    # Generic platform bucket (TTS cache). Server-side only: no browser reaches it, so it
    # needs neither CORS nor public access.
    gcs_platform_bucket: str = ""
    bhsa_data_path: str = ""

    cleaning_api_url: str = ""
    cleaning_api_key: str = ""

    inngest_event_key: str = ""
    inngest_signing_key: str = ""

    password_reset_token_expire_minutes: int = 60
    email_provider: str = "log"
    resend_api_key: str = ""

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    email_from_address: str = "support@shemaywam.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def qdrant_collection(self) -> str:
        return "meaning_map_prod" if self.env == "production" else "meaning_map_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
