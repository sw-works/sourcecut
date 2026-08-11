from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthorDefinition:
    author_id: str
    display_name: str


AUTHORS = {
    "Lewis": AuthorDefinition("lewis", "Meriwether Lewis"),
    "Clark": AuthorDefinition("clark", "William Clark"),
    "Gass": AuthorDefinition("gass", "Patrick Gass"),
}


def get_author(name: str) -> AuthorDefinition:
    try:
        return AUTHORS[name]
    except KeyError as error:
        raise ValueError(f"Unknown journal author: {name}") from error
