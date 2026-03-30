# Product-Ready Precision Recommendations

## Operating Modes
- sensitive: lower threshold, higher recall, expected lower PPV.
- precise: constrained precision threshold with recall floor and bal-acc guardrail.
- abstention-assisted: high-confidence outputs only; uncertain cases routed to manual review.

## Immediate Product Actions
- Deploy depression champion in precise mode; keep conduct/elimination in conservative mode.
- For elimination, mark output explicitly as exploratory due to PPV ceiling and instability.
