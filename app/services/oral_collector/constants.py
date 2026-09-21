from app.core.config import get_settings

GCS_OC_PROJECT = "gen-lang-client-0886209230"


def gcs_oc_bucket() -> str:
    return get_settings().gcs_oc_bucket
