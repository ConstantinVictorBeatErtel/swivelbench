# Verifiers adapter

Thin `StatefulToolEnv` over SwivelBench domains (`CB-*` / `GR-*`, including
Track A step ids like `CB-SEED-001@S1_template`).

```bash
uv pip install 'swivelbench[verifiers]'
python -c "from adapters.verifiers import load_environment; print(load_environment(['CB-SEED-001@S1_template']))"
python -m adapters.verifiers.smoke --task CB-SEED-001
python -m adapters.verifiers.smoke --task CB-SEED-001@S3_model
python -m adapters.verifiers.smoke --task GR-SEED-001
```

`load_environment(task_ids=...)` requires all task ids from one domain.
Default `prefer_steps=True` loads step episodes when `task_ids` is omitted.
RL reward = `criterion_pass_rate`; `task_passed` and `saturated_hint` are in
state / `reward_detail`.
