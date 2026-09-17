import contextlib
import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None


async def init_qdrant() -> None:
    global _client
    settings = get_settings()

    _client = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
    )

    collection_name = settings.qdrant_collection
    try:
        if not await _client.collection_exists(collection_name):
            await _client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection '%s'", collection_name)

        with contextlib.suppress(UnexpectedResponse, Exception):
            await _client.create_payload_index(
                collection_name=collection_name,
                field_name="namespace",
                field_schema=PayloadSchemaType.KEYWORD,
            )
            await _client.create_payload_index(
                collection_name=collection_name,
                field_name="doc_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
    except Exception:
        logger.warning(
            "Could not connect to Qdrant at '%s'. "
            "RAG endpoints will fail until Qdrant is reachable.",
            settings.qdrant_url,
        )
        _client = None


def get_qdrant_client() -> AsyncQdrantClient:

    if _client is None:
        raise RuntimeError("Qdrant client not initialised — call init_qdrant() first")
    return _client


async def close_qdrant() -> None:

    global _client
    if _client is not None:
        await _client.close()
        _client = None
