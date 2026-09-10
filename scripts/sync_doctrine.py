"""Vendor Marcia's doctrine and her prompts at a pinned commit, or check them for drift.

`docs/DOCTRINE.md` is binding on every change to this repository, and §5.1 says who owns
what: "`prompts/*.md`, the model ladder and its parameters are **Marcia's artifacts**: any
change is a ruling with her word, never an engineering default." Neither the doctrine nor her
prompts were in this repo, so the rule governing the work lived where a developer could not
open it.

They are vendored here, not forked. The bytes come from one commit of her repository, the pin
records repo, branch, commit and a sha256 per file, and an edit to a vendored file is a merge
conflict rather than a decision. Her prompts land beside ours — `prompts/vendor/` next to
`prompts/` — because ours are derived from hers and have diverged on purpose; replacing ours
would throw away the tickets that ported her text, and the vendoring exists so that "how does
our Guide prompt differ from hers" is a `diff` instead of an argument.

`--sync` reads her working tree rather than the network: the repository is private, and a
token in CI would be a second way in for something that is meant to move by hand, deliberately,
when she has ruled. Point it at a checkout of `fia/pilot-2026-09`.

    uv run python scripts/sync_doctrine.py --check             # offline; CI runs this
    uv run python scripts/sync_doctrine.py --sync --from ~/src/Tripod-Internalization
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

REPO = "shemaobt/Tripod-Internalization"
BRANCH = "fia/pilot-2026-09"

#: Her path in `Tripod-Internalization` → the path it is vendored to here.
VENDORED = {
    "docs/DOCTRINE.md": "docs/doctrine/vendor/DOCTRINE.md",
    "prompts/guide_system_prompt.md": (
        "app/services/internalization_room/prompts/vendor/guide_system_prompt.md"
    ),
    "prompts/validator_system_prompt.md": (
        "app/services/internalization_room/prompts/vendor/validator_system_prompt.md"
    ),
    "prompts/classifier_system_prompt.md": (
        "app/services/internalization_room/prompts/vendor/classifier_system_prompt.md"
    ),
    "prompts/book_overview_system_prompt.md": (
        "app/services/internalization_room/prompts/vendor/book_overview_system_prompt.md"
    ),
    "prompts/fail_safe_utterances.md": (
        "app/services/internalization_room/prompts/vendor/fail_safe_utterances.md"
    ),
}

PIN_FILE = REPO_ROOT / "docs/doctrine/DOCTRINE_PIN"
RULINGS_DIR = REPO_ROOT / "docs/doctrine/rulings"
SEAM_FILE = REPO_ROOT / "docs/doctrine/MODEL_SEAM"

#: Where the room asks a model anything. Narrower than `check_doctrine.SCAN_ROOTS` on purpose:
#: §5.1 is about the ladder the room runs on, and the other services have ladders of their own.
SEAM_ROOTS = ("app/services/internalization_room", "app/api/internalization_room")
SEAM_SETTINGS = ("tripod_voice_model", "tripod_analysis_model", "tripod_classifier_model")

#: The four parameters of a model call §5.1 reserves to her. `schema` and `system_prompt` are
#: the caller's business; these four are what "the ladder and its parameters" names.
GOVERNED = ("ladder", "max_output_tokens", "effort", "thinks")

#: A row whose third column is this is an inherited default, frozen at today's value rather
#: than credited to a ruling she never made. Moving one is a diff a reviewer cannot miss.
UNRULED = "unruled"

OWNERSHIP = (
    "DOCTRINE.md §5.1 — prompts/*.md, the model ladder and its parameters are Marcia's "
    "artifacts: any change is a ruling with her word, never an engineering default."
)
NOT_A_FORK = (
    "DOCTRINE.md is vendored, not forked: a vendored artefact is re-synced, never edited. "
    "Restore the bytes, or re-pin with --sync and record her ruling."
)


@dataclass(frozen=True)
class Pin:
    repo: str
    branch: str
    commit: str
    digests: dict[str, str]


@dataclass(frozen=True)
class Ruling:
    slug: str
    pin: str
    governs: str
    word: str
    written: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_pin(pin_file: Path = PIN_FILE) -> Pin:
    fields: dict[str, str] = {}
    digests: dict[str, str] = {}
    for line in pin_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        head, _, rest = line.partition(" ")
        if head in ("repo", "branch", "commit"):
            fields[head] = rest.strip()
        else:
            digests[rest.strip()] = head
    return Pin(
        repo=fields.get("repo", ""),
        branch=fields.get("branch", ""),
        commit=fields.get("commit", ""),
        digests=digests,
    )


def write_pin(commit: str, digests: dict[str, str], pin_file: Path = PIN_FILE) -> None:
    lines = [f"repo {REPO}", f"branch {BRANCH}", f"commit {commit}", ""]
    lines += [f"{digests[path]}  {path}" for path in sorted(digests)]
    pin_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def drift(pin: Pin, root: Path = REPO_ROOT) -> list[str]:
    """Every vendored path whose bytes are not the ones the pin recorded.

    Walked over `VENDORED` rather than over the pin, because the pin is the thing being
    checked: dropping a row and its file together is otherwise a vendored artefact that
    silently stops being one, with the comparison green for having nothing left to compare.
    """
    drifted = []
    for path in sorted(VENDORED.values()):
        local = root / path
        if path not in pin.digests:
            drifted.append(f"unpinned: {path}")
        elif not local.exists():
            drifted.append(f"missing: {path}")
        elif digest(local.read_bytes()) != pin.digests[path]:
            drifted.append(f"edited: {path}")
    return drifted


def read_rulings(rulings_dir: Path = RULINGS_DIR) -> list[Ruling]:
    rulings = []
    for path in sorted(rulings_dir.glob("*.md")):
        fields: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, rest = line.partition(":")
            if sep and key.strip() in ("pin", "governs", "word", "written"):
                fields[key.strip()] = rest.strip()
        rulings.append(
            Ruling(
                slug=path.stem,
                pin=fields.get("pin", ""),
                governs=fields.get("governs", ""),
                word=fields.get("word", ""),
                written=fields.get("written", ""),
            )
        )
    return rulings


def unruled(pin: Pin, rulings: list[Ruling]) -> list[str]:
    """What the pin and the rulings beside it fail to account for.

    A re-sync rewrites every sha in the pin, so drift alone can never catch one: the bytes
    and their record move together. What cannot move quietly is the commit — so a pin naming
    a commit no ruling names is the re-sync nobody recorded her word for.
    """
    faults = []
    if not any(ruling.pin == pin.commit for ruling in rulings):
        faults.append(f"no ruling records the pin {pin.commit[:12]}")
    for ruling in rulings:
        if not ruling.word or not ruling.written:
            faults.append(f"{ruling.slug}: a ruling carries her sentence and where it is written")
    return faults


def _call_agent_defaults(root: Path) -> dict[str, str]:
    tree = ast.parse((root / "app/services/internalization_room/llm.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "call_agent":
            named = node.args.kwonlyargs
            return {
                arg.arg: ast.unparse(default)
                for arg, default in zip(named, node.args.kw_defaults, strict=True)
                if arg.arg in GOVERNED and default is not None
            }
    return {}


def model_seam(root: Path = REPO_ROOT) -> dict[str, str]:
    """Every governed model parameter the room chooses, keyed by where it is chosen.

    Read with `ast`, never with a line-shaped regex, and keyed by the enclosing function rather
    than by a line: `doctrine_allowlist` records what a line-keyed register costs when eighteen
    tickets touch one file. A site that names none of the four parameters still appears, with
    `call_agent`'s own defaults spelled out — a budget inherited is a budget chosen.
    """
    seam: dict[str, str] = {}
    config = root / "app/core/config.py"
    for node in ast.walk(ast.parse(config.read_text())):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id in SEAM_SETTINGS
            and node.value is not None
        ):
            seam[f"app/core/config.py::{node.target.id}"] = ast.literal_eval(node.value)

    defaults = _call_agent_defaults(root)
    for scanned in SEAM_ROOTS:
        for path in sorted((root / scanned).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            enclosing: list[str] = []

            def visit(node: ast.AST, rel: str = rel, enclosing: list[str] = enclosing) -> None:
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    enclosing.append(node.name)
                    for child in ast.iter_child_nodes(node):
                        visit(child)
                    enclosing.pop()
                    return
                if isinstance(node, ast.Call):
                    func = node.func
                    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                    if name == "call_agent":
                        chosen = dict(defaults)
                        chosen.update(
                            {
                                keyword.arg: ast.unparse(keyword.value)
                                for keyword in node.keywords
                                if keyword.arg in GOVERNED
                            }
                        )
                        if chosen.get("ladder") == "None":
                            chosen["ladder"] = "voice_ladder(settings)"
                        spelled = " ".join(f"{k}={chosen[k]}" for k in GOVERNED if k in chosen)
                        seam[f"{rel}::{enclosing[-1]}"] = spelled
                for child in ast.iter_child_nodes(node):
                    visit(child)

            visit(ast.parse(path.read_text()))
    return seam


def read_seam_record(seam_file: Path = SEAM_FILE) -> dict[str, tuple[str, str]]:
    record: dict[str, tuple[str, str]] = {}
    for line in seam_file.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        key, value, ruling = (part.strip() for part in line.split("  ") if part.strip())
        record[key] = (value, ruling)
    return record


def seam_drift(record: dict[str, tuple[str, str]], live: dict[str, str]) -> list[str]:
    faults = []
    for key in sorted(set(record) | set(live)):
        if key not in live:
            faults.append(f"vanished: {key} — the record names a model call that is gone")
        elif key not in record:
            faults.append(f"unrecorded: {key} — {live[key]}")
        elif record[key][0] != live[key]:
            faults.append(f"moved: {key} — {record[key][0]} → {live[key]}")
    return faults


def unnamed_rulings(record: dict[str, tuple[str, str]], rulings: list[Ruling]) -> list[str]:
    written = {ruling.slug for ruling in rulings}
    return [
        f"{key}: no ruling {ruling}"
        for key, (_value, ruling) in sorted(record.items())
        if ruling != UNRULED and ruling not in written
    ]


def sync(source: Path) -> int:
    commit = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    digests: dict[str, str] = {}
    for hers, ours in sorted(VENDORED.items()):
        data = (source / hers).read_bytes()
        target = REPO_ROOT / ours
        target.parent.mkdir(parents=True, exist_ok=True)
        moved = "new" if not target.exists() else ("moved" if target.read_bytes() != data else "")
        target.write_bytes(data)
        digests[ours] = digest(data)
        print(f"  {ours}{f' ({moved})' if moved else ''}")
    write_pin(commit, digests)
    print(f"pinned at {commit}")
    return 0


def check() -> int:
    pin = read_pin()
    faults = drift(pin)
    if faults:
        print(f"the vendored doctrine drifted from pin {pin.commit[:12]}:", file=sys.stderr)
        for line in faults:
            print(f"  {line}", file=sys.stderr)
        print(NOT_A_FORK, file=sys.stderr)
        return 1

    rulings = read_rulings()
    record = read_seam_record()
    missing = (
        unruled(pin, rulings) + seam_drift(record, model_seam()) + unnamed_rulings(record, rulings)
    )
    if missing:
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        print(OWNERSHIP, file=sys.stderr)
        return 1

    inherited = sum(1 for _value, ruling in record.values() if ruling == UNRULED)
    print(f"the vendored doctrine matches pin {pin.commit[:12]}")
    print(f"the model seam matches its record — {inherited} of {len(record)} rows still unruled")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--sync", action="store_true")
    group.add_argument("--check", action="store_true")
    parser.add_argument("--from", dest="source", type=Path)
    args = parser.parse_args()
    if args.sync and args.source is None:
        parser.error("--sync needs --from <checkout of Tripod-Internalization>")
    return sync(args.source) if args.sync else check()


if __name__ == "__main__":
    raise SystemExit(main())
