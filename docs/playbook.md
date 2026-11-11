# How to read an A/B test before you believe it

A one-page checklist. If a test fails a question, the questions after it
barely matter. Written from the experiments in this repository; every
question has a worked example in `results/`.

## 1. Was assignment random — and by user?
Randomization is what makes the comparison fair. Assignment by day, store or
region instead of user needs a different analysis (clustered errors) and much
more caution. *Unclear assignment = not an experiment; read it like
observational data.*

## 2. Does the split match the intended split? (sample ratio check)
Compare observed group counts to the intended ratio with a chi-square test.
A p-value below 0.001 means the randomization or the logging is broken —
stop and investigate before reading any lift.
*Worked examples: `results/srm.csv` — all six studies pass or are recorded
as "intended split undocumented".*

## 3. Was the outcome chosen before looking?
A metric picked after peeking will be the one that happened to move.
This project committed `analysis_plan.md` (outcomes, inclusion rules, what
counts as "no effect") before any analysis ran; the git timestamp is the proof.

## 4. Was the test big enough? (power / minimum detectable effect)
Compute the smallest lift the test could reliably detect (MDE). A null result
from a test whose MDE is larger than any plausible effect means
**"we could not tell"**, never "there is no effect".

## 5. Is the result an interval, not only a p-value?
"Lift 0.12 pp, 95% CI 0.11–0.12" says the size and the uncertainty;
"p < 0.05" says neither. Lead with the interval. Distrust any readout
that hides it.

## 6. Everyone assigned, nobody dropped? (intention to treat)
Dropping users who were assigned ads but never saw them breaks the
randomization — the exposed are systematically different people. Compare
everyone assigned vs everyone assigned, even if it dilutes the lift.

## 7. How many segments were examined — and corrected for?
Twenty segments at α=0.05 produce one false "winner" on average. Demand the
count of segments examined and a correction (Bonferroni or Benjamini–
Hochberg). *Worked example: `results/segments_hillstrom.csv` states m=8 and
the BH verdict per segment.*

## 8. Is the lift worth the cost? (incremental CPA / ROAS)
Divide spend by **incremental** conversions (the lift × treated size), not by
all conversions among the exposed. The honest CPA is usually several times
the attributed one.

## 9. Did it run a full cycle?
Anything shorter than one complete week (better: two) confounds the
treatment with day-of-week. Watch for tests stopped early "because it was
already significant" — that inflates false positives.

## 10. What decision does each outcome trigger, written in advance?
"If the CI excludes +2%, scale; if it excludes +5% at the top, stop; else
extend two weeks." If no decision was written down, the test was theatre.

---
*Ad Measurement Study — public datasets, personal project.*
