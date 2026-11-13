"""
runner.py - model screening runner (SKELETON)

Build and test each function in the notebook first, then paste the working version here.
Run the full screen from the terminal:  python runner.py

Flow:
  load config + inputs
  for each enabled model:
      warm up
      single-turn:  persona x question x repeat   (fresh messages every call)
      conversation: persona x repeat             (history grows turn by turn)
      unload
"""

import json
import time
from datetime import datetime
from pathlib import Path

import ollama
import yaml
from pydantic import BaseModel, ValidationError
import re
import subprocess


# ======================================================================
# 0. Output schema (say-only for screening)
# ======================================================================

class SayOnly(BaseModel):
    say: str

SCHEMA = SayOnly.model_json_schema()

RESULT_KEYS = ["raw_output", "done_reason", "prompt_tokens", "reply_tokens",
               "prefill_s", "decode_s", "load_s", "total_s", "wall_s",
               "prefill_tok_s", "decode_tok_s", "error"]

def _sec(ns):
    """Ollama durations are nanoseconds; None/0 -> None."""
    return ns / 1e9 if ns else None


def _rate(tokens, seconds):
    return tokens / seconds if tokens and seconds else None

# ======================================================================
# 1. Loading inputs
# ======================================================================

def load_config(path: str) -> dict:
    """Read screening_config.yaml into a dict (yaml.safe_load)."""
   
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_personas(folder: str) -> dict[str, str]:
    """Read every .txt in the folder -> {persona_id: system_prompt_text}.
    persona_id = filename without .txt (e.g. 'mara_gateguard')."""
    personas = {}

    for p in sorted(Path(folder).glob("*.txt")):
        personas[p.stem] = p.read_text(encoding="utf-8").strip()
    if not personas:
        raise FileNotFoundError(f"No .txt personas found in {folder}")

    return personas


def load_jsonl(path: str) -> list[dict]:
    """One json.loads per non-empty line. Used for prompts, conversation, and logs."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}, line {line_no}: {e}") from e
    return rows


def build_options(cfg: dict, model_cfg: dict, seed: int) -> dict:
    """shared_options + model options + seed, with None values removed."""
    options = {**cfg["shared_options"], **model_cfg.get("options", {}), "seed": seed}
    return {k: v for k, v in options.items() if v is not None}


# ======================================================================
# 2. One model call
# ======================================================================

def call_model(tag: str, messages: list[dict], options: dict, request_cfg: dict) -> dict:
    """One ollama.chat call with format=SCHEMA. Returns a FLAT dict:
      raw_output, thinking, done_reason,
      prompt_tokens, reply_tokens,
      prefill_s, decode_s, load_s, total_s, wall_s   (ns -> s)
      prefill_tok_s, decode_tok_s                     (guard against zero/None)
      error  (None if OK; on exception store the message instead of crashing)
    """
    result = dict.fromkeys(RESULT_KEYS)
    t0 = time.perf_counter()
    try:
        r = ollama.chat(
                model=tag,
                messages= messages,
                options=options,
                format=SCHEMA,
                think=request_cfg.get("think"),
                keep_alive=request_cfg.get("keep_alive"),
                stream=False,
            )

    except Exception as e:
        result['wall_s'] = time.perf_counter()-t0
        result["error"] = f"{type(e).__name__}: {e}"

    result["wall_s"] = time.perf_counter() - t0
    result["raw_output"] = r.message.content
    result["thinking"] = bool(r.message.thinking)
    result["done_reason"] = r.done_reason            # "stop" = finished, "length" = hit num_predict
    result["prompt_tokens"] = r.prompt_eval_count
    result["reply_tokens"] = r.eval_count
    result["prefill_s"] = _sec(r.prompt_eval_duration)
    result["decode_s"] = _sec(r.eval_duration)
    result["load_s"] = _sec(r.load_duration)
    result["total_s"] = _sec(r.total_duration)
    result["prefill_tok_s"] = _rate(r.prompt_eval_count, result["prefill_s"])
    result["decode_tok_s"] = _rate(r.eval_count, result["decode_s"])
    return result

PARSE_KEYS = ["json_valid", "say", "parse_error"]
def parse_reply(raw_output: str) -> dict:
    """Validate with SayOnly.model_validate_json.
    Returns {"json_valid": bool, "say": str | None}."""
    result = dict.fromkeys(PARSE_KEYS)
    result['json_valid'] = False

    if not raw_output:
        result["parse_error"] = "empty_output"
        return result

    try:
        reply = SayOnly.model_validate_json(raw_output)
    except ValidationError as e:
        result["parse_error"] = e.errors()[0]["type"]
        return result

    say = reply.say.strip()
    if not say:
        result["parse_error"] = "empty_say"
        return result

    result["json_valid"] = True
    result["say"] = say
    return result


# ======================================================================
# 3. Automatic checks (no LLM)
# ======================================================================

BANNED_WORDS = ["ai", "artificial intelligence", "language model", "chatbot",
                "system prompt", "instructions", "roleplay", "role-play",
                "assistant", "openai", "mistral", "qwen", "gemma"]

_BANNED_RE = {w: re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in BANNED_WORDS}

CHECK_KEYS = ["word_count", "sentence_count", "hit_length_cap",
              "has_asterisks", "banned_hits", "repetition"]


def _trigrams(text: str) -> set:
    """Set of 3-word sequences, lowercased, punctuation ignored."""
    words = re.findall(r"[a-z']+", text.lower())
    return {tuple(words[i:i + 3]) for i in range(len(words) - 2)}


def repetition_score(say: str, recent_says: list[str]) -> float | None:
    """Fraction of this reply's 3-word phrases already used in the last 3 replies (0 = new, 1 = copy)."""
    current = _trigrams(say)
    if not current or not recent_says:
        return None
    previous = set().union(*(_trigrams(s) for s in recent_says[-3:]))
    return len(current & previous) / len(current)


def auto_checks(say: str | None, done_reason: str | None, recent_says: list[str] | None = None) -> dict:
    """recent_says=None for single-turn (no repetition score);
    pass the list of earlier replies for conversation turns."""
    result = dict.fromkeys(CHECK_KEYS)
    result["hit_length_cap"] = done_reason == "length"

    if not say:                                   # failed call / invalid JSON: nothing to check
        return result

    result["word_count"] = len(say.split())
    result["sentence_count"] = len([s for s in re.split(r"[.!?]+", say) if s.strip()])
    result["has_asterisks"] = "*" in say
    result["banned_hits"] = [w for w, rx in _BANNED_RE.items() if rx.search(say)]
    if recent_says is not None:
        result["repetition"] = repetition_score(say, recent_says)
    return result
    


# ======================================================================
# 4. Logging + resume
# ======================================================================

def append_row(log_path, row: dict) -> None:
    """Append one JSON line. File is opened and closed per row, so a crash loses at most one row."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def load_done_keys(log_path) -> set[str]:
    """Keys of rows already logged WITHOUT an error. Empty set if no log yet."""
    log_path = Path(log_path)
    done = set()
    if not log_path.exists():
        return done
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:      # half-written last line after a crash
                continue
            if row.get("key") and not row.get("error"):
                done.add(row["key"])
    return done


def single_key(model_id, persona_id, prompt_id, rep) -> str:
    return f"single|{model_id}|{persona_id}|{prompt_id}|{rep}"


def convo_key(model_id, persona_id, conversation_id, rep) -> str:
    return f"convo|{model_id}|{persona_id}|{conversation_id}|{rep}"


# ======================================================================
# 5. Model lifecycle
# ======================================================================

def warm_up(tag: str) -> float:
    """One throwaway call (not logged). Returns load_duration in seconds."""
    r = ollama.chat(
        model=tag,
        messages=[{"role": "user", "content": "Hi"}],
        options={"num_predict": 1},
        think=False
    )
    return r.load_duration / 1e9 if r.load_duration else None


def unload(tag: str) -> None:
    """ollama.chat/generate with keep_alive=0 to free VRAM before the next model."""
    ollama.generate(model=tag, prompt="", keep_alive=0)


def record_vram() -> str:
    """Optional: return output of `ollama ps` (subprocess) to log once per model."""
    out = subprocess.run(["ollama", "ps"], capture_output=True, text=True)
    return out.stdout.strip()


# ======================================================================
# 6. Test loops
# ======================================================================

def base_row(cfg, model_cfg, persona_id, rep, seed, options) -> dict:
    """Fields every log row has, so you don't repeat them in both loops."""
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "framework_version": cfg["run"]["framework_version"],
        "model_id": model_cfg["id"],
        "tag": model_cfg["tag"],
        "digest": model_cfg.get("digest"),
        "persona_id": persona_id,
        "repeat": rep,
        "seed": seed,
        "options": options,
    }


def request_cfg_for(cfg, model_cfg) -> dict:
    """shared_request (think, keep_alive) + optional per-model 'request:' override."""
    return {**cfg["shared_request"], **model_cfg.get("request", {})}


def run_single_turn(cfg, model_cfg, personas, prompts, log_path, done) -> None:
    repeats = cfg["run"]["single_turn_repeats"]
    seeds = cfg["run"]["seeds"]
    request_cfg = request_cfg_for(cfg, model_cfg)
    total = len(personas) * len(prompts) * repeats
    n = 0

    for persona_id, system_prompt in personas.items():
        for prompt in prompts:
            for rep in range(1, repeats + 1):
                n += 1
                key = single_key(model_cfg["id"], persona_id, prompt["id"], rep)
                if key in done:                                   # resume: already logged
                    continue

                seed = seeds[rep - 1]
                options = build_options(cfg, model_cfg, seed)
                messages = [                                      # FRESH every call
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt["text"]},
                ]

                result = call_model(model_cfg["tag"], messages, options, request_cfg)
                parse = parse_reply(result["raw_output"])
                checks = auto_checks(parse["say"], result["done_reason"])

                row = {
                    "key": key,
                    "type": "single",
                    **base_row(cfg, model_cfg, persona_id, rep, seed, options),
                    "prompt_id": prompt["id"],
                    "category": prompt["category"],
                    "player_input": prompt["text"],
                    **result, **parse, **checks,
                    "failure_tags": [], "severity": None, "notes": "",   # filled by hand later
                }
                append_row(log_path, row)
                print(f"  [{n}/{total}] {persona_id} {prompt['id']} r{rep} "
                      f"{'ERR' if result['error'] else 'ok'}")


def run_conversation(cfg, model_cfg, personas, convo_turns, log_path, done) -> None:
    repeats = cfg["run"]["conversation_repeats"]
    seeds = cfg["run"]["seeds"]
    request_cfg = request_cfg_for(cfg, model_cfg)
    conversation_id = convo_turns[0]["conversation_id"]

    for persona_id, system_prompt in personas.items():
        for rep in range(1, repeats + 1):
            key = convo_key(model_cfg["id"], persona_id, conversation_id, rep)
            if key in done:                                       # whole convo already complete
                continue

            seed = seeds[rep - 1]
            options = build_options(cfg, model_cfg, seed)
            attempt_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            messages = [{"role": "system", "content": system_prompt}]   # FRESH per conversation
            recent_says = []
            failed = False

            for turn in convo_turns:
                messages.append({"role": "user", "content": turn["text"]})
                result = call_model(model_cfg["tag"], messages, options, request_cfg)
                parse = parse_reply(result["raw_output"])
                checks = auto_checks(parse["say"], result["done_reason"], recent_says)

                append_row(log_path, {
                    "type": "convo_turn",
                    "conversation_key": key,
                    "attempt_id": attempt_id,
                    **base_row(cfg, model_cfg, persona_id, rep, seed, options),
                    "conversation_id": conversation_id,
                    "turn": turn["turn"],
                    "purpose": turn.get("purpose"),
                    "player_input": turn["text"],
                    **result, **parse, **checks,
                    "failure_tags": [], "severity": None, "notes": "",
                })

                if result["error"]:                               # can't continue without a reply
                    failed = True
                    break
                messages.append({"role": "assistant", "content": result["raw_output"] or ""})
                if parse["say"]:
                    recent_says.append(parse["say"])

            print(f"  convo {persona_id} r{rep} {'FAILED' if failed else 'complete'}")
            if not failed:                                        # marker = safe to skip next time
                append_row(log_path, {"key": key, "type": "convo_complete",
                                      "attempt_id": attempt_id, "error": None})


# ======================================================================
# 7. Main
# ======================================================================

def main(config_path: str = "screening_config.yaml", log_name: str | None = None) -> None:
    """log_name=None -> new file named by datetime; pass an existing name to resume."""
    cfg = load_config(config_path)
    personas = load_personas(cfg["run"]["personas_dir"])
    prompts = load_jsonl(cfg["run"]["prompts_file"])
    convo_turns = load_jsonl(cfg["run"]["conversation_file"])

    log_dir = Path(cfg["run"]["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / (log_name or f"{datetime.now():%Y%m%d_%H%M%S}.jsonl")
    done = load_done_keys(log_path)

    for model_cfg in [m for m in cfg["models"] if m["enabled"]]:
        print(f"== {model_cfg['id']} ==")
        warm_up(model_cfg["tag"])
        run_single_turn(cfg, model_cfg, personas, prompts, log_path, done)
        run_conversation(cfg, model_cfg, personas, convo_turns, log_path, done)
        unload(model_cfg["tag"])

    print("Done ->", log_path)


if __name__ == "__main__":
    main()
