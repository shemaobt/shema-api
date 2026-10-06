"""The copy held two of the three artifacts of each passage and no names list. At her compile of
29 September it holds, for Ruth, each passage's Meaning Map, Meaning Coordinates and Compilation
Log and the book's aliases list: 43 files, the share of her 114 that belongs to the one book
served today. The checksums are the ones her own `VENDOR_MANIFEST.json` records at the same pin
(ENG-1201).
"""

from __future__ import annotations

import hashlib

from app.services.internalization_room.canon.parse_map import VENDOR

STEMS = (
    "P01-Ruth-1-1-5",
    "P02-Ruth-1-6-14",
    "P03-Ruth-1-15-18",
    "P04-Ruth-1-19-22",
    "P05-Ruth-2-1-7",
    "P06-Ruth-2-8-16",
    "P07-Ruth-2-17-23",
    "P08-Ruth-3-1-5",
    "P09-Ruth-3-6-13",
    "P10-Ruth-3-14-18",
    "P11-Ruth-4-1-8",
    "P12-Ruth-4-9-12",
    "P13-Ruth-4-13-17",
    "P14-Ruth-4-18-22",
)

COORDINATES_SHA256 = {
    "P01-Ruth-1-1-5": "a3d70765c20cea71c1c4694fa376f0841dc0c5a795f20fb0fb82da57edcc760c",
    "P02-Ruth-1-6-14": "56a8e5493d26c8f51a7fa71a898925d00e9062f72c8ff82f31626ff81fe69e28",
    "P03-Ruth-1-15-18": "51f204a2187d55aa889c9fd4ab59cff636fad6c9d4516a74f68cefe2e170dfe5",
    "P04-Ruth-1-19-22": "d603277862c81eead4234ca702cec69bd38e961ec32553698a838d5d442cec55",
    "P05-Ruth-2-1-7": "31710e868c60c27e8013dab10cd15c3a6d4653edceb98c84bbd32936945d3dcc",
    "P06-Ruth-2-8-16": "779b61b2e80b154f5014c8098bc5a6032b891a09e7a9430087805ba1fc311602",
    "P07-Ruth-2-17-23": "1204276d5a4147148f7712db7092f776b1602b14ea014c36a559e227e972d09e",
    "P08-Ruth-3-1-5": "62dde8807b0671868038413ee134142d7767971a9ff5c9d4225850e46f6bb3bb",
    "P09-Ruth-3-6-13": "45abd1d7454cf56104d6f033026c11d62c8426762e4429acc74f03dfec858842",
    "P10-Ruth-3-14-18": "cb973a4b85a70e297f0a93beb818b129e99c96b4985be28d7e7970eb602a0b33",
    "P11-Ruth-4-1-8": "4a1968e36b8ac558aeead86b2f4ce28bc2033d8f2c13c376522a3421219cab99",
    "P12-Ruth-4-9-12": "9fd7c1eb846d17baf00522f074198e965567864c1b019b74f31ae8abf4e7a925",
    "P13-Ruth-4-13-17": "12562ab1fb7d179a0cb3a5bdd8bbde06b927787c1b3eacaf06df0045019f3c1c",
    "P14-Ruth-4-18-22": "7d8b760ced8753d785e2d5cc63d73a962a9155337413cfab383260065b0ebc55",
}

RUTH_ALIASES_SHA256 = "6bd2550f0c5c38e879c506111ee55757588acacbaeb6df8708b393887cf1412c"


def _sha256(path: str) -> str:
    return hashlib.sha256((VENDOR / path).read_bytes()).hexdigest()


def test_every_passage_of_ruth_has_its_map_its_coordinates_and_its_log() -> None:
    held = sorted(str(path.relative_to(VENDOR)) for path in VENDOR.rglob("*") if path.is_file())

    assert held == sorted(
        ["VENDOR_PIN", "registry/ruth.aliases.json"]
        + [f"meaning-map/{stem}.md" for stem in STEMS]
        + [f"meaning-coordinates/{stem}-MEANING-COORDINATES.md" for stem in STEMS]
        + [f"compilation-log/{stem}-COMPILATION-LOG.md" for stem in STEMS]
    )


def test_her_coordinates_for_ruth_are_byte_for_byte_the_ones_her_manifest_records() -> None:
    held = {stem: _sha256(f"meaning-coordinates/{stem}-MEANING-COORDINATES.md") for stem in STEMS}

    assert held == COORDINATES_SHA256


def test_the_aliases_list_of_ruth_is_byte_for_byte_the_one_her_manifest_records() -> None:
    assert _sha256("registry/ruth.aliases.json") == RUTH_ALIASES_SHA256
