import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mints_a_clip_address(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "to_handle"
    if isinstance(node, ast.Attribute):
        return node.attr == "to_handle"
    if isinstance(node, ast.alias):
        return node.name == "to_handle"
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
