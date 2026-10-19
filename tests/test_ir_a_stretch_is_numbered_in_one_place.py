import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
NUMBERING = "app/services/internalization_room/back_translation.py"


def _numbers_stretches_from_one(call: ast.Call) -> bool:
    named = isinstance(call.func, ast.Name) and call.func.id == "enumerate"
    from_one = any(
        keyword.arg == "start"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value == 1
        for keyword in call.keywords
    )
    over = call.args[0] if call.args else None
    stretches = (isinstance(over, ast.Name) and over.id in {"told", "segments"}) or (
        isinstance(over, ast.Call)
        and isinstance(over.func, ast.Name)
        and over.func.id == "told_back"
    )
    return named and from_one and stretches


def test_a_stretch_is_numbered_in_one_function_and_nowhere_else() -> None:
    numbering = sorted(
        str(path.relative_to(APP.parent))
        for path in APP.rglob("*.py")
        if any(
            isinstance(node, ast.Call) and _numbers_stretches_from_one(node)
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        )
    )

    assert numbering == [NUMBERING], (
        "a frase era numerada em mais de um lugar, e cada um é livre para discordar da voz"
    )
