"""GCS configuration for the Sound Necklace's private objects.

A dedicated bucket, provisioned private (uniform bucket-level access, public-access
prevention enforced), so nothing a facilitator or a listener produces is reachable
without a signed URL. The name is configuration, not a secret — same as
``annotation_studio/constants.py``.
"""

from app.db.models.sound_necklace import ArtifactKind

GCS_SN_BUCKET = "sound-necklace-private"

# PRD §10 freezes these filenames — the downstream pipeline reads them by name. They
# ride in the object key rather than in a Content-Disposition header: a browser
# following the download redirect derives the saved filename from the URL path, so the
# pipeline gets the name it expects without the API ever touching the bytes.
ARTIFACT_FILENAMES: dict[ArtifactKind, str] = {
    ArtifactKind.MANIFEST: "manifesto-contas.json",
    ArtifactKind.ANCHORING: "retorno-ancoragem.json",
    ArtifactKind.REPORT: "relatorio-mapeamento.md",
}

ARTIFACT_CONTENT_TYPES: dict[ArtifactKind, str] = {
    ArtifactKind.MANIFEST: "application/json",
    ArtifactKind.ANCHORING: "application/json",
    ArtifactKind.REPORT: "text/markdown; charset=utf-8",
}

DOWNLOAD_URL_EXPIRY_MINUTES = 15

# A voice answer is a short spoken reply in WebM/Opus — well under a megabyte in
# practice. The cap is a guard against a client bug or the wrong file being sent, not a
# real expected size; it is enforced before a byte reaches storage.
VOICE_ANSWER_CONTENT_TYPE = "audio/webm"
MAX_VOICE_ANSWER_BYTES = 10 * 1024 * 1024
