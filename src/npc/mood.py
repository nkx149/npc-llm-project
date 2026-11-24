"""Mood logic: tone labels, tone -> delta lookup, mood bands.

Pure, deterministic logic. Standard library only; imports nothing of ours.
"""
from enum import Enum


class Tone(str, Enum):
    """Label the LLM assigns to the player's message."""
    hostile = "hostile"
    cold = "cold"
    neutral = "neutral"
    friendly = "friendly"
    warm = "warm"


class MoodBand(str, Enum):
    """Coarse mood category shown to the game and described in words in the prompt."""
    # TODO: decide band names; these are placeholders.
    hostile = "hostile"
    unfriendly = "unfriendly"
    neutral = "neutral"
    friendly = "friendly"
    very_friendly = "very friendly"


MOOD_MIN = -10
MOOD_MAX = 10


# Need's tuning
TONE_DELTA: dict[Tone, int] = {
    Tone.hostile: -5,
    Tone.cold: -2,
    Tone.neutral: 0,
    Tone.friendly: 2,
    Tone.warm: 5,
}
assert set(TONE_DELTA) == set(Tone), "every Tone needs a TONE_DELTA entry"


def mood_change(mood: int, tone: Tone) -> int:
    new_mood = max(MOOD_MIN, min(MOOD_MAX, mood + TONE_DELTA[tone]))
    return new_mood


def band(mood: int) -> MoodBand:
    """Map an integer mood (MOOD_MIN..MOOD_MAX) to its MoodBand."""
    # TODO: fixed band thresholds
    raise NotImplementedError


if __name__ == "__main__":
    # Manual check: run from src/ with `python -m npc.mood`
    for tone in Tone:
        print(tone.value, mood_change(0, tone))
