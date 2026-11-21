# Batch C: why recovery is slow (diagnosis)

- Source: the per-second counts of Batches A and B (seeds 301 to 305, already run) and a trace of what v6.1 believes,
  second by second, on pilot seed 101 (`feedback/batchC/trace.py`). No evaluation run was made for this note.

## What is slow

The 20 s after each event ends, v6.1 against round-robin + admission at 0.90 without smoothing (seeds 301 to 305):

| Event end | v6.1 success / rejected | Tuned rival success / rejected |
|---|---|---|
| Beirut, burst ends (80 s) | 78.1% / 20.0% | 89.2% / 8.4% |
| New network, burst ends (80 s) | 83.5% / 13.4% | 90.8% / 4.9% |
| Beirut, surge ends (100 s) | 86.8% / 11.2% | 90.4% / 6.3% |
| Beirut, DC gets 4 servers back (110 s) | 74.4% / 20.4% | 95.7% / 0.0% |
| Beirut, Hamra gets its server back (100 s) | 94.1% / 0.3% | 83.3% / 0.0% |
| New, Regional DC gets 2 servers back (100 s) | 87.4% / 1.6% | 70.1% / 0.0% |

## Two causes, both seen in the trace (pilot seed 101)

1. **The traffic estimate comes down slowly after a burst.** Burst on Beirut, 140% from 60 s to 80 s:
   - at 84 s to 90 s v6.1 believes 171 to 187 frames/s while the truth is 123 to 135 (1.35 to 1.39 times);
   - it still drops 23% of frames at 87 s, with the load back at 85%;
   - the estimate is within 6% of the truth only from about 111 s, 30 s after the burst.
   - Reason in the code (`catsim/rules_v61.py`, `_absorb`): a clear rise is taken at once, but a fall only moves
     the estimate 30% of the way at each report (every 5 s on Beirut).
2. **The capacity meter is slow to see servers come back.** DC loses 4 of 8 servers from 50 s to 110 s:
   - the meter reads 4 servers from 57 s, and still reads 4 at 135 s; 5 at 138 s;
   - so v6.1 keeps dropping about 20% of frames after the servers are back.
   - Reason in the code (`catsim/rules.py`, `SpeedMeter`): a site measured slower gets one server back after a quiet
     spell of max(20 s, 4 W) seconds, one server at a time.

## The one fix chosen to work on

- Cause 1, the estimate. It also explains where v6.1 is clearly behind the tuned rival (three burst scenarios),
  and the tuned rival differs exactly in reacting at once. Cause 2 affects one scenario of Batch A.
- Cause 2 is left as a known limit and reported.
- Candidates and the rule of the choice: `feedback/batchC/design.py` (written before the pilot runs).
