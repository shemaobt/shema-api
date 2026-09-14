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
    anthropic_api_key: str = ""
    #: The workspace an identity-bound key acts in, sent as the `anthropic-workspace-id`
    #: header. A Console key tied to a person is not scoped to a workspace on its own, and
    #: every call under one answers 400 until the workspace is named; a classic workspace key
    #: carries its own scope and wants this empty, so it is a value the deployment supplies
    #: rather than a branch in the code.
    anthropic_workspace_id: str = ""
    google_embedding_model: str = "gemini-embedding-001"
    google_llm_model: str = "gemini-3.1-pro-preview"
    #: The two Gemini tiers every feature speaks through. They were literals in nine
    #: modules, so the model behind Translation Helper, Project Health, the
    #: Internalization Room, Sound Necklace and i18n could only be changed by editing and
    #: deploying nine files — and all nine named a preview. A preview is withdrawn without
    #: notice, and with no alerting in front of them the first sign would have been five
    #: features failing at once. Here, moving off one is an environment variable.
    gemini_fast_model: str = "gemini-3-flash-preview"
    gemini_quality_model: str = "gemini-3-flash-preview"
    #: The room's three model ladders, most capable first, comma-separated. A ladder rather
    #: than one id because a key is not entitled to every model: the room steps down a rung
    #: when the API answers that this key cannot use the one above, and only then — a rate
    #: limit keeps the rung it is on. The voice carries the Guide and the Validator, and
    #: DOCTRINE.md forbids anything but a frontier model there; analysis reads the telling
    #: back against the map; the classifier only moves beads and runs off the voice path.
    #: These and their parameters are Marcia's artifacts (DOCTRINE.md 5.1), not ours to tune.
    tripod_voice_model: str = "claude-fable-5-1,claude-opus-5,claude-opus-4-8"
    tripod_analysis_model: str = "claude-fable-5-1,claude-opus-5,claude-opus-4-8"
    tripod_classifier_model: str = "claude-sonnet-5,claude-sonnet-4-6"
    rag_chunk_size: int = 1000
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5

    elevenlabs_api_key: str = ""
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v2"
    elevenlabs_output_format: str = "mp3_44100_128"

    ph_elevenlabs_api_key: str = ""

    internalization_room_api_key: str = ""
    #: What her golden runner presents to drive the room by text instead of by microphone.
    #: Empty is the production configuration: the text seam then does not exist, and its
    #: routes answer 404 rather than asking for a credential nobody has been given.
    internalization_room_runner_key: str = ""
    #: The room bills its own voice. Empty falls back to the shared key.
    internalization_room_elevenlabs_api_key: str = ""
    #: The room's Portuguese voice. One native voice per language it speaks, never one
    #: multilingual voice for all of them: a voice keeps its accent in any language, and a
    #: Brazilian-cloned voice reading English is the failure ``platform/voices.py`` argues
    #: against at length.
    internalization_room_voice_id: str = "83Nae6GFQiNslSbuzmE7"
    internalization_room_voice_id_en: str = "x52Gqgso2pdbdr7KngsJ"
    internalization_room_voice_id_es: str = "fYypSok4m8xKqKsDwS7O"
    #: What a caller that names no language gets. Not "the language the room speaks" any
    #: more — the app names that on the session, because it is the tablet that knows which
    #: language the team in front of it reads its own settings in.
    internalization_room_default_language: str = "en"
    internalization_room_tts_model: str = "eleven_turbo_v2_5"
    internalization_room_voice_stability: float = 0.45
    internalization_room_voice_similarity: float = 0.85
    internalization_room_voice_style: float = 0.10
    internalization_room_voice_speed: float = 0.96

    gcs_bucket_name: str = ""
    # Generic platform bucket (TTS cache). Server-side only: no browser reaches it, so it
    # needs neither CORS nor public access.
    gcs_platform_bucket: str = ""
    bhsa_data_path: str = ""

    cleaning_api_url: str = ""
    cleaning_api_key: str = ""

    inngest_event_key: str = ""
    inngest_signing_key: str = ""
    #: The app Inngest registers this deploy under. It was a literal, which made every
    #: service built from this image the same app: the sync writes the serve endpoint of
    #: the id it is given, so a second service registering as `tripod-backend` takes
    #: production's endpoint and production's events start arriving at it. Staging sets
    #: this; the default is production, so an unset variable deploys what it always did.
    inngest_app_id: str = "tripod-backend"

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
