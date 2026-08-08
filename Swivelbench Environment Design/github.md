repo: ConstantinVictorBeatErtel/swivelbench
branch: main

## Last sync
date: 2026-08-08T22:06:00Z

### Updated in this project
- Built the commercial-banking run explorer from the CB step map and assertions
- Built the grading run explorer from the GR step map and assertions
- Both pages bake in a real baseline run (nemotron-3-super-120b, 2026-08-08)
- Artifact chips download real .xlsx / .docx from /samples/...
- Format checks F1/F2 (CB) and F1 (GR) explain Office-file formatting success/failure

## Screen map
| Screen | Built from |
| --- | --- |
| Commercial Banking.dc.html | viz/maps/commercial_banking.json, envs/commercial_banking/fixtures/assertions.sql, eval/results/baseline-20260808-135321.json, viz/samples/cb/* |
| Grading.dc.html | viz/maps/grading.json, envs/grading/fixtures/assertions.sql, eval/results/baseline-20260808-135715.json, viz/samples/gr/* |
