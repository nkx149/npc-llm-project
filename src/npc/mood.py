
from enum import Enum
import bisect
import math


class Tone(str, Enum):
    """Label the LLM assigns to the player's message."""
    hostile = "hostile"
    cold = "cold"
    neutral = "neutral"
    friendly = "friendly"
    warm = "warm"


class MoodBand(str, Enum):
    """Coarse mood category shown to the game and described in words in the prompt."""
    hostile = "hostile"
    unfriendly = "unfriendly"
    neutral = "neutral"
    friendly = "friendly"
    very_friendly = "very friendly"


MOOD_MIN = -10
MOOD_MAX = 10

MOOD_BAND_BOUNDS = (-7, -2, 2, 6)
MOOD_BANDS = (MoodBand.hostile, MoodBand.unfriendly, 
              MoodBand.neutral, MoodBand.friendly, MoodBand.very_friendly)

# Need's tuning
TONE_DELTA: dict[Tone, float] = {
    Tone.hostile: -2.0,
    Tone.cold: -1.0,
    Tone.neutral: 0,
    Tone.friendly: 1.0,
    Tone.warm: 2.0,
}
assert set(TONE_DELTA) == set(Tone), "every Tone needs a TONE_DELTA entry"


def mood_change(mood: float, tone: Tone, delta: dict[Tone, float] = TONE_DELTA) -> float:
    new_mood = max(MOOD_MIN, min(MOOD_MAX, mood + delta[tone]))
    return new_mood

def mood_decay(mood:float, rate: float, baseline: float = 0.0) -> float:
    return baseline + (mood - baseline) * (1-rate)

def return_mood_band(mood: float) -> MoodBand:
    """
    Bisecting right returns number of values <= mood in array, 
    That would be the index number of the current mood band curerntly in MOOD_BANDS
    """
    return MOOD_BANDS[bisect.bisect(MOOD_BAND_BOUNDS, mood)]


def band(mood: float, currentBand: MoodBand) -> MoodBand:
    """Map an integer mood (MOOD_MIN..MOOD_MAX) to its MoodBand."""
    HYSTERESIS_CONSTANT = 1.0
    i = MOOD_BANDS.index(currentBand)
    if i > 0:
        low = MOOD_BAND_BOUNDS[i-1] - HYSTERESIS_CONSTANT
    else:
        low = -math.inf

    if i < len(MOOD_BAND_BOUNDS):
        high = MOOD_BAND_BOUNDS[i] + HYSTERESIS_CONSTANT
    else:
        high = math.inf

    if low <= mood <= high:
        return currentBand

    return return_mood_band(mood)




if __name__ == "__main__":
    # Manual check: run from src/ with `python -m npc.mood`
    mood_band = band(2.9, currentBand=MoodBand.neutral)

    print (mood_band)
