"""What a budget attachment may be: ten types, one ceiling, proof by signature.

GATE-03 D3 (27/aug/2026) made the attachment a real file, and the client answered the
format question on 28/aug/2026: *"PDF, planilha e documento de texto (limite de mb tem
que ser algo razoável)"*. The ten content types below are that answer spelled out —
PDF; spreadsheet as .xlsx, .xls, .ods, .csv; text document as .docx, .doc, .odt, .rtf,
.txt — and the ceiling the client delegated is recorded in OBT-474 as **10 MB**.

**Extension is never consulted.** A filename is client-typed text and renaming
``malware.exe`` to ``orcamento.pdf`` costs nothing; what is checked is the declared
content type *and* the bytes' own signature, and the two must agree.

**The container formats are told apart from the inside, not by their outer magic.**
.xlsx, .docx, .ods and .odt all open with the same four bytes (``PK\\x03\\x04`` — they
are ZIP archives), so the outer signature proves only *a ZIP*. The archive is opened and
read: an ODF file carries a ``mimetype`` member whose content **is** its content type,
and an OOXML file carries ``[Content_Types].xml`` naming ``spreadsheetml`` or
``wordprocessingml``. .xls and .doc are both OLE2 the same way; there the split is the
stream marker at byte 512, which is what ``filetype``'s two matchers read.

**The signature library is ``filetype``, and the choice is recorded here** because the
issue asked for the reason: ``filetype`` is pure Python, so the Docker image does not
move; ``python-magic`` binds ``libmagic``, which would put a system package into the
Dockerfile for a check this module needs on ten types only. Where ``filetype``'s ZIP
heuristics fall short of the issue's bar (it matches OOXML by byte offsets instead of
reading the archive), the archive is opened here instead.
"""

import io
import zipfile

import filetype

from app.core.exceptions import ValidationError

#: The delegated "algo razoável", decided at 10 MB and recorded in OBT-474 (28/aug/2026).
#: The router refuses over the ceiling with 413 **before reading the body**; the check
#: here is the backstop for any caller that is not the router.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

#: The ten accepted content types, and the extension each one puts on the storage key.
#: The extension comes from this table — server-owned — never from the client's filename.
ATTACHMENT_EXTENSIONS: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.oasis.opendocument.spreadsheet": ".ods",
    "text/csv": ".csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/vnd.oasis.opendocument.text": ".odt",
    "application/rtf": ".rtf",
    "text/plain": ".txt",
}

_ZIP_MAGIC = b"PK\x03\x04"
_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

#: OOXML: `[Content_Types].xml` declares the parts, and the part namespace names the
#: application. A .docx never mentions spreadsheetml and a .xlsx never mentions
#: wordprocessingml, so one marker each is a positive identification.
_OOXML_MARKERS: dict[str, bytes] = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": b"spreadsheetml",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": b"wordprocessingml",
}

#: ODF: the `mimetype` member's content is the container's own content type, verbatim.
_ODF_TYPES = frozenset(
    {
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.text",
    }
)

_TEXT_TYPES = frozenset({"text/csv", "text/plain"})

#: The C0 control bytes a text file has no business carrying. Tab, LF and CR are text;
#: everything else below 0x20 — and DEL — is the trace of a binary payload wearing
#: `text/plain`. Checked as **bytes**, never char by char over a decoded string: at the
#: 10 MB ceiling the Python-level loop cost 5.8 s of blocked event loop against 102 ms
#: for `bytes.translate`, measured on the same buffer. It is also exact on both codecs
#: below — no multi-byte UTF-8 sequence contains a byte under 0x80, and cp1252 maps
#: 0x00 to 0x1F and 0x7F to those same control characters.
_TEXT_CONTROL_BYTES = (
    bytes(code for code in range(0x20) if code not in (0x09, 0x0A, 0x0D)) + b"\x7f"
)

#: UTF-8 first, then the code page a Brazilian Excel writes. A .csv exported from Excel on
#: a pt-BR Windows is cp1252, and one header cell reading `orçamento` is already enough to
#: fail a strict UTF-8 decode — a 400 on one of the formats the client listed as *planilha*.
#: cp1252 rather than latin-1 keeps the refusal reachable: five bytes (0x81, 0x8D, 0x8F,
#: 0x90, 0x9D) are undefined in it, where latin-1 accepts all 256 and would make the arm
#: dead code. The security intent never lived in the decode anyway — it lives in the
#: control-byte scan above, which is what a binary renamed to .txt fails.
_TEXT_CODECS = ("utf-8", "cp1252")


def attachment_type(declared: str | None, data: bytes) -> str:
    """The canonical content type of an acceptable attachment, or ``ValidationError``.

    Both halves must hold: ``declared`` (parameters such as ``; charset=utf-8``
    stripped) must be one of the ten, and ``data`` must carry that type's signature —
    a declared type the bytes contradict is refused, never trusted.

    **Two of the ten have no signature to check, and that is a property of the formats
    rather than a gap here:** .csv and .txt are bare text, with no magic number anywhere
    in the file. The proof for them is the one available: the bytes carry no control
    characters outside ``\\t``, ``\\r`` and ``\\n`` — which is what separates a text file
    from a binary one renamed — and they decode as UTF-8 or as cp1252.
    """
    if declared is None or not declared.strip():
        raise ValidationError(
            "The attachment needs a Content-Type header naming one of the accepted formats."
        )
    canonical = declared.split(";", 1)[0].strip().lower()
    if canonical not in ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported attachment type: {canonical}. "
            f"Accepted: {', '.join(sorted(ATTACHMENT_EXTENSIONS))}"
        )
    if not data:
        raise ValidationError("The attachment is empty.")

    if canonical in _TEXT_TYPES:
        _prove_text(canonical, data)
    elif canonical in _ODF_TYPES or canonical in _OOXML_MARKERS:
        _prove_zip_container(canonical, data)
    else:
        _prove_by_filetype(canonical, data)
    return canonical


def _refused(canonical: str) -> ValidationError:
    return ValidationError(
        f"The file's content does not match the declared type {canonical}: "
        "its signature identifies a different format."
    )


def _prove_text(canonical: str, data: bytes) -> None:
    """The no-signature proof for .csv and .txt, as the module docstring records.

    The control scan runs first: it is the half that carries the intent, and it is the
    cheaper of the two on the buffer that arrives here.
    """
    if len(data.translate(None, _TEXT_CONTROL_BYTES)) != len(data):
        raise ValidationError(
            f"A {canonical} attachment must be plain text; the file carries control "
            "bytes that text does not."
        )
    for codec in _TEXT_CODECS:
        try:
            data.decode(codec)
        except UnicodeDecodeError:
            continue
        return
    raise ValidationError(
        f"A {canonical} attachment must be UTF-8 or cp1252 text; the file decodes as neither."
    )


def _prove_zip_container(canonical: str, data: bytes) -> None:
    """Open the ZIP and read who it says it is — the outer magic proves only *a ZIP*."""
    if not data.startswith(_ZIP_MAGIC):
        raise _refused(canonical)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise _refused(canonical) from None

    with archive:
        member = "mimetype" if canonical in _ODF_TYPES else "[Content_Types].xml"
        try:
            content = archive.read(member)
        except KeyError:
            raise _refused(canonical) from None

    if canonical in _ODF_TYPES:
        if content.decode("ascii", errors="replace").strip() != canonical:
            raise _refused(canonical)
    elif _OOXML_MARKERS[canonical] not in content:
        raise _refused(canonical)


def _prove_by_filetype(canonical: str, data: bytes) -> None:
    """The remaining four — PDF, RTF, .xls, .doc — through ``filetype``'s matchers.

    PDF and RTF carry a leading magic the library reads whole. .xls and .doc share the
    OLE2 magic, so a bare magic check could not split them; the library's two matchers
    read the stream marker at byte 512 (Word's FIB, Excel's BOF), which is the
    inside-the-container check those formats admit.
    """
    if canonical in {"application/vnd.ms-excel", "application/msword"} and not data.startswith(
        _OLE2_MAGIC
    ):
        raise _refused(canonical)
    kind = filetype.guess(data)
    if kind is None or kind.mime != canonical:
        raise _refused(canonical)
