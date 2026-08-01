from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION_NAME = "tripod-backend"
FALLBACK_VERSION = "0.0.0+unknown"


def get_app_version() -> str:
    try:
        return version(DISTRIBUTION_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION
