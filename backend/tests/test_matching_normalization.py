import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest

FIXTURES = json.loads(
    (Path(__file__).resolve().parents[1] / "matching" / "normalization.json").read_text(
        encoding="utf-8"
    )
)["fixtures"]
APOSTROPHES = {"'", "’"}


def _alphanumeric(character: str) -> bool:
    # Approximates Rust's char::is_alphanumeric; fixtures avoid characters where they differ.
    return character.isalpha() or unicodedata.category(character) in {"Nd", "Nl", "No"}


def _ascii_digit(character: str) -> bool:
    return character.isascii() and character.isdigit()


def _oracle_tokens(text: str) -> list[str]:
    """Test oracle for the README rules. The Rust matcher is the product implementation."""
    text = text.lower()
    tokens: list[str] = []
    current: list[str] = []
    for index, character in enumerate(text):
        before = text[index - 1] if index > 0 else ""
        after = text[index + 1] if index + 1 < len(text) else ""
        if _alphanumeric(character):
            current.append(character)
        elif character in APOSTROPHES and current and after and _alphanumeric(after):
            continue
        elif character == "." and _ascii_digit(before) and _ascii_digit(after):
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def test_fixture_names_are_unique() -> None:
    names = [fixture["name"] for fixture in FIXTURES]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda fixture: fixture["name"])
def test_fixtures_follow_the_written_rules(fixture: dict[str, Any]) -> None:
    assert _oracle_tokens(fixture["input"]) == fixture["tokens"]
