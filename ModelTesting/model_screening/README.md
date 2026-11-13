# Model screening

```
model_screening/
├── README.md                  this file
├── screening_config.yaml      models, params, repeats, paths
├── personas/
│   ├── mara_gateguard.txt     hand-written system prompts (schema v0.1 field order)
│   └── wren_herbalist.txt
├── prompts.jsonl              15 single-turn questions (id, category, text, expect)
├── conversation.jsonl         15-turn scripted conversation (drift / consistency)
├── runner.py                  functions + main loop; run with `python runner.py`
├── build.ipynb                prototype each runner function on tiny inputs
├── analysis.ipynb             load log -> blind tagging sheet -> tables/plots
└── <log_dir>/                 one .jsonl per run (path set in config)
```

## Workflow
1. Fill config TODOs (digests, quant, params + source).
2. build.ipynb: implement and test one function at a time, then paste into runner.py.
3. Mini run: 1 model, 1 persona, 2 questions. Check the log, then run again to check resume.
4. Full run from terminal: `python runner.py`.
5. analysis.ipynb: export blind sheet, hand-tag repeat 1 + conversations, build codebook, apply decision rule.

## Run size
3 models x (2 personas x 15 questions x 2 repeats + 2 personas x 15 turns x 1 repeat) = 270 replies.
Hand-tag: repeat 1 + conversations = 180 replies.

## Decision rule (write final version before running)
- Hard gates: fits in VRAM at 100% GPU; median reply time < ~3 s; JSON valid >= 95%; no thinking leak.
- Then: lowest severity-weighted failure count. Close (within ~10%) -> faster/smaller model wins.
