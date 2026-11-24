
from pathlib import Path

from pydantic import BaseModel

from . import llm, mood, prompts
from .mood import MoodBand
from .paths import PERSONAS_DIR, SAVES_DIR
from .persona import Persona, load_persona
from .state import NPCState, load_state, save_state


class TurnResponse(BaseModel):
    """What the game receives after one turn."""
    npc_id: str
    reply: str
    mood_band: MoodBand


class NPCEngine:
    def __init__(self, personas_dir: Path = PERSONAS_DIR, saves_dir: Path = SAVES_DIR):
        self._personas_dir = personas_dir
        self._saves_dir = saves_dir
        self._personas: dict[str, Persona] = {}  # persona_id -> static persona
        self._npcs: dict[str, NPCState] = {}     # npc_id -> dynamic state

    def add_npc(self, npc_id: str, persona_id: str) -> None:
        """Load the persona (once) and register a fresh NPCState for npc_id."""
        # TODO: implement (load_persona from self._personas_dir)
        raise NotImplementedError

    def take_turn(self, npc_id: str, player_text: str) -> TurnResponse:
        """One turn: build messages -> llm.chat -> mood.mood_change -> append history -> TurnResponse."""
        # TODO: implement
        raise NotImplementedError

    def save(self) -> None:
        """Save every registered NPC's state under self._saves_dir."""
        # TODO: implement (save_state per NPC)
        raise NotImplementedError

    def load(self) -> None:
        """Restore NPC states saved by save()."""
        # TODO: implement (load_state per file)
        raise NotImplementedError
