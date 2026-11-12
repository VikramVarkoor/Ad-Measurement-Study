# Findings summary

Generated from the results tables; every number below is
machine-verified by `src/verify_summary.py`.

## What marketing caused

Across 16.1 million users in six randomized experiments,
every treatment produced a real lift. Pooling the six studies with a
random-effects model gives a risk ratio of
1.32
(95% CI 1.18 to
1.48), with an I-squared of
99.7%: the studies genuinely disagree, so no
single pooled number transfers to a new channel.

The largest experiment, Criteo display advertising, moved conversion
from 0.194% in the control group to
0.309% in the treated group, an absolute
lift of 0.12 percentage points.

## Who to target

Ranking users by predicted uplift concentrates the effect: messaging
the top 20% keeps
68% of the incremental conversions on Criteo
(held-out data). On the much smaller Hillstrom test the model keeps
only 25%, barely above random, and is reported as weak.

## The e-commerce diagnosis

On the Olist marketplace, orders delivered more than three days late
average 1.86 stars against
4.29 stars for on-time orders. This is an association,
not a cause: no experiment randomized lateness.
