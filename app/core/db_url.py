from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def async_database_url(url: str) -> str:
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    parsed = urlparse(url)
    if parsed.query:
        params = parse_qs(parsed.query)
        params.pop("sslmode", None)
        params.pop("channel_binding", None)
        new_query = urlencode(params, doseq=True)
        url = urlunparse(parsed._replace(query=new_query))
    return url


def ssl_connect_args(original_url: str) -> dict[str, bool]:
    if "sslmode=require" in original_url or "sslmode=verify" in original_url:
        return {"ssl": True}
    return {}
