"""Data schemas for character sheet and validation results."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Error:
    code: str
    field: str
    expected: any
    actual: any
    message: str


@dataclass
class ValidationResult:
    valid: bool
    errors: list[Error] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    derived: dict = field(default_factory=dict)


# Attribute keys (8 main attributes, luck separate)
ATTR_KEYS = ["str", "con", "dex", "app", "pow", "siz", "edu", "int"]

# Attribute display names
ATTR_NAMES = {
    "str": "力量",
    "con": "体质",
    "dex": "敏捷",
    "app": "外貌",
    "pow": "意志",
    "siz": "体型",
    "edu": "教育",
    "int": "智力",
    "luc": "幸运",
}
