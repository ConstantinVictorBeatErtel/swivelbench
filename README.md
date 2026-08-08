# SwivelBench

Dual-system RL / eval environments for enterprise workflows. Agents act through
a typed tool API (no raw SQL). Reward is **final database correctness** —
deterministic SQL assertions over two ATTACHed SQLite systems. No LLM judge.

| Domain | Systems | Tasks |
|---|---|---|
| Commercial banking | `credit_workbench` + `ncino_core` | `CB-*` |
| Grading | `inbox` + `gradescope` | `GR-*` |

Sketch-aligned workflows (credit memo / Gradescope TA) with intentional mess:
corrupted templates, conflicting digests, spread injection, messy rubrics,
unclear answers, regrade bait. Excel (`.xlsx`) and Word (`.docx`) files are
written on top of the DB so rollouts leave real artifacts.

## Quick start

Python 3.11+, stdlib only for core:

```bash
python3 eval/oracle.py --task CB-SEED-001
python3 eval/oracle.py --task GR-SEED-001
python3 -m pytest tests/test_adversarial.py -v
```

Oracle must score `1.000`. Wrong states must score `< 0.60`.

### Model baselines (OpenRouter)

```bash
uv pip install openai pytest ruff
export OPENROUTER_API_KEY=sk-or-v1-...   # no wrapping quotes in the value
python3 -m eval.run_baseline \
  --models nvidia/nemotron-3-super-120b-a12b:free \
  --task CB-SEED-001 -k 1
```

Runs are kept under `eval/results/runs/` (DBs + xlsx/docx + `result.json`).

### Localhost app (Environment Design)

Baseline run explorers for Commercial Banking and Grading:

```bash
python3 -m viz.server --port 8765
# open http://127.0.0.1:8765          → Commercial Banking
#      http://127.0.0.1:8765/grading  → Grading
#      http://127.0.0.1:8765/runs     → live run picker (materialized runs)
```

```bash
python3 -m eval.materialize_run eval/results/baseline-YYYYMMDD-HHMMSS.json
```

## Scoring

| Kind | Share |
|---|---:|
| Positive | 18% |
| Propagation | 27% |
| Negative | 32% |
| Trail | 13% |
| Format | 10% |

Critical assertion failures cap `final` at `0.30` (benchmark). Set
`CRITICAL_CAP = None` for RL training.

Format checks (`F*`) unzip produced `.xlsx` / `.docx` files and score
structural Office formatting — see `docs/format_judgement.md`.

## Layout

```
core/                       db, BaseActionAPI, verifier, xlsx/docx writers
envs/commercial_banking/    credit request → spread → report → nCino
envs/grading/               email rubrics → Gradescope → regrades
envs/registry.py            CB-/GR- dispatch
eval/                       oracle, baseline, materialize
viz/                        localhost server + live run explorer
Swivelbench Environment Design/  main CB/GR baseline UI
adapters/verifiers/         optional Verifiers RL adapter
tests/                      adversarial suite
docs/env_graphs.md          workflow diagrams
```

## Verifiers adapter

```bash
uv pip install 'swivelbench[verifiers]'
python -c "from adapters.verifiers import load_environment; print(load_environment(['CB-SEED-001']))"
```

## Provenance

All data is synthetic. No real bank, customer, student, or institution data.

## License

MIT
