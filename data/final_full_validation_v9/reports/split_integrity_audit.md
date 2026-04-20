# Split Integrity Audit (v9)

## Coverage
- strict_full splits audited for adhd, anxiety, conduct, depression, elimination.
- Checks: overlap, duplicates, metadata drift, feature-hash overlaps.

- total_checks: 35
- flagged_checks: 0

No split integrity violations detected in participant overlap / duplication checks.

## Notes
- No family_id or visit_id columns exist in current strict dataset; family/visit leakage cannot be audited with current data schema.
