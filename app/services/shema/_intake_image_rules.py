"""What the Pulso Mensal's image may be: three formats, one ceiling, proof by signature.

OBT-578, Daniel's approval of 8/oct/2026 over the proposal: **JPEG, PNG and WebP, up to 10 MiB**,
and the bytes prove the type — the ``Content-Type`` a leader's phone declares is checked against
the file's own magic number and never trusted alone, the rule
``app/services/resource_request/_attachment_rules.py`` applies to the form's attachment. SVG
is out (an XML document that scripts can live in, and no reader here would render it safely);
AVIF is out because the console only *accepts* it on the client, and a format the server cannot
prove is a format it does not take.

The ceiling is a ceiling on an **unauthenticated** write: the link is the whole guard, and a
forwarded link must not be a way to fill the bucket. The console reduces a photo to 1200px WebP
before sending (``src/services/mediaStorage.ts``), so the ordinary upload is a few hundred KB and
the ceiling is never met by a real one.
"""

from __future__ import annotations

from typing import Final

from app.core.exceptions import ValidationError

MAX_IMAGE_BYTES: Final = 10 * 1024 * 1024

#: Canonical type → extension of the object key.
IMAGE_EXTENSIONS: Final[dict[str, str]] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _is_png(data: bytes) -> bool:
    return data[:8] == b"\x89PNG\r\n\x1a\n"


def _is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"


_PROOF = {"image/jpeg": _is_jpeg, "image/png": _is_png, "image/webp": _is_webp}


def image_type(declared: str | None, data: bytes) -> str:
    """The canonical content type of an acceptable image, or ``ValidationError``.

    Both halves must hold: ``declared`` (parameters stripped) must be one of the three, and
    ``data`` must carry that type's signature — a declared type the bytes contradict is refused.
    The size is checked here too, after the body was already capped on the way in
    (``app/api/shema/forms.py``), so a caller of this function alone is protected as well.
    """
    if declared is None or not declared.strip():
        raise ValidationError("The image needs a Content-Type header naming jpeg, png or webp.")
    canonical = declared.split(";", 1)[0].strip().lower()
    if canonical == "image/jpg":
        canonical = "image/jpeg"
    if canonical not in IMAGE_EXTENSIONS:
        raise ValidationError(
            f"Unsupported image type: {canonical}. Accepted: {', '.join(sorted(IMAGE_EXTENSIONS))}"
        )
    if not data:
        raise ValidationError("The image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValidationError(
            f"The image is {len(data)} bytes and the Pulse accepts "
            f"{MAX_IMAGE_BYTES // (1024 * 1024)} MB. Nothing was kept."
        )
    if not _PROOF[canonical](data):
        raise ValidationError(
            f"The file's content does not match the declared type {canonical}: "
            "its signature identifies a different format."
        )
    return canonical
