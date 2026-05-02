# v17 Extreme Metrics Threshold/Separability Audit

- generated_at_utc: `2026-05-02T16:05:25.779857+00:00`
- audited_extreme_slots_count: `30`
- leakage_confirmed_count: `0`
- target_proxy_confirmed_count: `0`
- split_contamination_confirmed_count: `0`
- threshold_adjustment_recommended_count: `0`
- threshold_adjustment_applied_count: `0`
- retrain_required_count: `0`
- unresolved_issue_count: `0`
- final_audit_status: `pass`

## Decision policy
- High metrics (>0.98) are treated as `high_separability_alert`, not automatic fail.
- Hard fail is only set for confirmed leakage/proxy/split contamination/runtime issues or unresolved corrections.
