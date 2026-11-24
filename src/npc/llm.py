"""LLM output schemas and the chat call. The ONLY module that imports ollama.

Holds no NPC state, no registry and no turn logic.
"""
from pathlib import Path
from functools import cache

import ollama
import yaml
from pydantic import BaseModel


from .mood import Tone
from .paths import RUNTIME_CONFIG_PATH


class NPCTurnOutput(BaseModel):
    """Structured output for single-call mode: classify the player's tone and reply."""
    player_tone: Tone
    say: str

# Two-call mode later: add e.g. ToneClassification(player_tone) and NPCReply(say) here.

@cache
def load_config(path: str | Path = RUNTIME_CONFIG_PATH) -> dict:
    """Read runtime.yaml and return the active model's tag, merged options and request settings."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    run = cfg["run"]
    active = run["active_model"]
    if active not in cfg["models"]:
        raise ValueError(f"active_model {active!r} not in models: {list(cfg['models'])}")
    model = cfg["models"][active]
    request = cfg.get("shared_request", {})

    return {
        "model": model["tag"],
        "options": {**cfg.get("shared_options", {}), **model.get("options", {}), "seed": run["seed"]},
        "think": request.get("think"),
        "keep_alive": request.get("keep_alive"),
    }


def chat(messages: list[dict], schema: type[BaseModel]) -> BaseModel:
    """Send `messages` to Ollama with `format=schema.model_json_schema()` and
    return the reply validated as `schema`.

    Schema-agnostic on purpose, so two-call mode only adds schemas, not new call code.
    """
    # TODO: implement (ollama.chat + schema.model_validate_json)

    chat_response = ollama.chat(
        **load_config(),
        messages=messages,
        format=schema.model_json_schema,
    )
    return schema.model_validate_json(chat_response.message.content)

