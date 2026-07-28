"""GCS configuration for annotation-studio audio + export bundles.

A dedicated bucket (separate from oral-collector's ``tripod-image-uploads``)
so the experiment's audio is isolated and its CORS is managed independently.
Storage keys are the *logical* keys built by ``naming.py`` (e.g.
``ter/tier_a/raw/<id>.wav``) and are used verbatim as object names.
"""

GCS_AS_BUCKET = "annotation-studio-audio"
GCS_AS_PROJECT = "gen-lang-client-0886209230"

SIGNED_PUT_EXPIRY_SECONDS = 600
SIGNED_GET_EXPIRY_SECONDS = 3600

# Upper bound for a single uploaded clip/recording. The presigned PUT URL is
# itself unconstrained, so this is enforced server-side at the "complete" step:
# an object larger than this is deleted instead of being marked STORED. Studio
# audio is short 16 kHz WAV, so 25 MB is generous headroom.
MAX_AUDIO_BYTES = 25 * 1024 * 1024
