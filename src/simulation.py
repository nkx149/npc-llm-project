"""Terminal frontend. Talks to npc.engine only.

Run from src/: `python -m repl`
"""
from npc.engine import NPCEngine


def main() -> None:
    engine = NPCEngine()
    # TODO: register NPC(s), then loop: read input -> engine.take_turn -> print reply + mood band
    raise NotImplementedError


if __name__ == "__main__":
    main()
