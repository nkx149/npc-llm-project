"""Dynamic per-NPC state (mood, history) and JSON save/load.

Imports mood only. Static persona data is referenced by `persona_id`, never embedded.
"""
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .mood import MOOD_MAX, MOOD_MIN


class Message(BaseModel):
    """One conversation turn, in Ollama chat-message shape."""
    role: Literal["user", "assistant"]
    content: str


class NPCState(BaseModel):
    npc_id: str
    persona_id: str
    mood: int = Field(default=0, ge=MOOD_MIN, le=MOOD_MAX)
    history: list[Message] = Field(default_factory=list)


def save_state(state: NPCState, path: str | Path) -> None:
    """Write one NPC's state to `path` as JSON."""
    # TODO: implement (state.model_dump_json)
    raise NotImplementedError


def load_state(path: str | Path) -> NPCState:
    """Read one NPC's state from a JSON file written by save_state."""
    # TODO: implement (NPCState.model_validate_json)
    raise NotImplementedError
