"""Static persona data: who the NPC is. Loaded from YAML; never saved with game state.

Imports nothing of ours.
"""
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ExampleDialogue(BaseModel):
    context: str | None = None
    player: str
    npc: str


class Persona(BaseModel):
    schema_version: float  # NOTE: YAML files use `0.1`; switch to str if versions ever reach x.10
    id: str
    name: str
    age: str
    gender: str
    race: str | None = None
    species: str

    role: str
    appearance: str
    personality: str
    background: str
    speech_style: str
    knowledge: str
    knowledge_boundaries: str

    secrets: str | None = None

    example_dialogue: list[ExampleDialogue] = Field(default_factory=list)

    @field_validator("example_dialogue", mode="before")
    @classmethod
    def none_to_empty(cls, v):
        return v or []


def load_persona(persona_path: str | Path) -> Persona:
    with open(persona_path, encoding="utf-8") as f:
        persona_data = yaml.safe_load(f)

    persona = Persona.model_validate(persona_data)

    return persona


if __name__ == "__main__":
    # Manual check: run from src/ with `python -m npc.persona`
    from .paths import PERSONAS_DIR

    print(load_persona(PERSONAS_DIR / "eric_blacksmith_persona.yaml").model_dump_json(indent=2))
