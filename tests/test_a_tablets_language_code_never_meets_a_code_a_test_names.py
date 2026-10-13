import ast
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from tests.device_harness import a_linked_tablet

TESTS = Path(__file__).resolve().parent


async def test_the_language_a_tablets_team_is_given_always_has_a_code_of_three_digits(
    db_session: AsyncSession,
) -> None:
    for _ in range(40):
        await a_linked_tablet(db_session)

    codes = list((await db_session.execute(select(Language.code))).scalars())

    assert len(codes) == 40
    assert all(re.fullmatch(r"[0-9]{3}", code) for code in codes), codes


def test_no_language_code_a_test_names_is_made_of_digits_alone() -> None:
    named: list[tuple[str, str]] = []
    for module in sorted(TESTS.rglob("*.py")):
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            literals: list[ast.expr] = []
            if isinstance(node, ast.keyword) and node.arg == "code":
                literals = [node.value]
            elif isinstance(node, ast.arguments):
                positional = [*node.posonlyargs, *node.args]
                pairs = [
                    *zip(
                        positional[len(positional) - len(node.defaults) :],
                        node.defaults,
                        strict=True,
                    ),
                    *zip(node.kwonlyargs, node.kw_defaults, strict=True),
                ]
                literals = [value for arg, value in pairs if arg.arg == "code" and value]
            elif (
                isinstance(node, ast.Constant) and isinstance(node.value, str) and "@" in node.value
            ):
                named.append((module.name, node.value[:3]))
            named.extend(
                (module.name, literal.value)
                for literal in literals
                if isinstance(literal, ast.Constant) and isinstance(literal.value, str)
            )

    assert [(module, code) for module, code in named if code.isdigit()] == []
