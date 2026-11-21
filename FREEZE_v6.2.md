# Freeze of ours v6.2 and of the final evaluation

Frozen before any run of v6.2 on an evaluation seed, and before any run of Batch D or on seeds 306 to 320.

## What v6.2 is

- v6.1 with ONE change: a clear fall of the traffic at a site (arrivals below what the estimate implies by more than
  3 standard deviations of a Poisson count) is taken at once, as a clear rise already was in v6.1. Without a clear
  change, the estimate is smoothed as in v6.1 (weight 0.3).
- Why: after a burst, v6.1's estimate stayed too high for about 30 s (`feedback/batchC/diagnosis.md`).
- How it was chosen: four candidates on pilot seeds 101 to 105, by rules committed before the pilot runs
  (`feedback/batchC/design.py`, result `feedback/batchC/choice.json`): +0.72 +- 0.17 points over v6.1 on the 22
  Batch A scenarios, pilot seeds; identical to v6.1 in every steady scenario.
- Code: `catsim/rules_v62.py` (new file), run name `ours_v62`. v6.1 and every file of `FREEZE_v6.1.md` are unchanged.
- Not fixed (a known limit): the capacity meter is slow to see servers come back.

## The final evaluation (`catsim/final.py`)

- Seeds 301 to 320. 301 to 310 are the evaluation seeds of the v6.1 freeze. **311 to 320 are added after the freeze
  of v6.1**: never used for anything before.
- Batch A: the 22 scenarios, 10 rules (the 7 of the v6.1 freeze, the two rivals tuned on pilot seeds, ours v6.2).
- Batch B: the 14 scenarios, 6 rules (the 4 of the v6.1 freeze, the tuned rival, ours v6.2).
- Batch D (new): fast on/off traffic and a 200 ms deadline, at loads 95% and 115%, on the three networks: 12
  scenarios, 5 rules (ours v6.2, ours v6.1, the tuned rival, the frozen rival, round-robin).
- Runs already made on seeds 301 to 305 are reused as they are.
- The rules of the analysis are those of the v6.1 freeze: deadline success; paired by seed; 95% interval from
  Student's t (19 degrees of freedom on 20 seeds); every scenario reported; nothing removed.

## Fingerprints (SHA-256)

| File | SHA-256 |
|---|---|
| `catsim/rules_v62.py` | `1223d570ef0457c100d2007d0a034bfdc6e7eea78320d6b17b1fc21097c0b606` |
| `catsim/final.py` | `057a857969abd574058041c15d4eaceafa2e9e5c6985c2028624a766785b583f` |
| `feedback/batchC/design.py` | `99f3805d8f4ea5291cff6ecd283c92f0771062676e5e77c4724f133577e26a0f` |
| `feedback/batchC/choice.json` | `edcf0667d89342db5c53ac0c52ee1fa5ef579440659bb08ae6df3c54a376ad87` |
| `feedback/final/run_final.py` | `24aa4b78301cfadf182c21564f6c3e58ec7f41c9010a849e55da6fc1a61775f8` |
| `tests/test_v62.py` | `21e62b79cd820b4265212a389453de5f7defaa78d4966cef09c4efa5a4304426` |
