# Verifiers adapter

Thin `StatefulToolEnv` over SwivelBench domains (`CB-*` or `GR-*`).

```bash
uv pip install 'swivelbench[verifiers]'
python -c "from adapters.verifiers import load_environment; print(load_environment(['CB-SEED-001']))"
python -m adapters.verifiers.smoke --task CB-SEED-001
python -m adapters.verifiers.smoke --task GR-SEED-001
```

`load_environment(task_ids=...)` requires all task ids from one domain.
`for_training=True` (default) disables `CRITICAL_CAP`.
