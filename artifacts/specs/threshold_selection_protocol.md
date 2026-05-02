# Threshold Selection Protocol

For each disorder model evaluate thresholds in [0.05, 0.95] step 0.01.

1) Youden J optimization
- J = sensitivity + specificity - 1
- choose threshold maximizing J when balanced operating point is desired.

2) F1 optimization
- choose threshold maximizing F1 when precision-recall tradeoff is priority.

3) Sensitivity-prioritized
- choose lowest threshold meeting target sensitivity (e.g. >=0.85), then maximize specificity.

Always report calibration status and final selected threshold rationale per disorder.
