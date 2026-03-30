# Operating Modes Spec

This file defines three operational modes for the app output layer.

1) sensitive
- threshold strategy: lower threshold than recommended
- expected tradeoff: higher recall, lower precision
- use case: screening-first workflows
- risk notes: more false positives

2) precise
- threshold strategy: higher threshold than recommended
- expected tradeoff: higher precision, lower recall
- use case: prioritize positive predictive value
- risk notes: more false negatives

3) abstention_assisted
- threshold strategy: recommended threshold + uncertainty band in inference layer
- expected tradeoff: balanced operating point with uncertain cases flagged
- use case: triage with human review
- risk notes: lower coverage due to abstention zone

- models covered: 14
