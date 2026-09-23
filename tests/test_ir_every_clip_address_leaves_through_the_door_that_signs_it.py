import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


#: What a module needs to build a clip address by hand: the encoder, or the route prefix the
#: signed address is appended to. Either one reaching a module other than `voice_handles`
#: is an address that could leave unsigned.
_MINTING_NAMES = {"to_handle", "ROUTE"}


def _mints_a_clip_address(node: ast.AST) -> bool:
    if isinstance(node, ast.ImportFrom):
        return (node.module or "").endswith("voice_handles") and any(
            alias.name in _MINTING_NAMES for alias in node.names
        )
    if isinstance(node, ast.Name):
        return node.id == "to_handle"
    if isinstance(node, ast.Attribute):
        return node.attr == "to_handle" or (
            node.attr == "ROUTE"
            and isinstance(node.value, ast.Name)
            and node.value.id == "voice_handles"
        )
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "internalization-room/voice" in node.value
    return False


def test_no_module_but_the_handles_own_mints_a_clip_address_past_clip_url() -> None:
    minting = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "app").rglob("*.py")
        if any(_mints_a_clip_address(node) for node in ast.walk(ast.parse(path.read_text())))
    }

    assert minting == {"app/services/internalization_room/voice_handles.py"}, (
        "um endereço de clipe montado fora de clip_url sairia sem assinatura e a rota o recusaria"
    )
