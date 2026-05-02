# Slice Hardening Analysis (v10)

- fragile_slices_input: 5
- slices_evaluated: 5
- corrected_yes: 0
- corrected_partial: 2
- corrected_no: 3

## Best slice gains
- psychologist/elimination source_mix=mid_gap: BA 0.6964 -> 0.7580 (delta=0.0616), global BA at best=0.7988, status=partial
- caregiver/depression site=Staten Island: BA 0.8434 -> 0.8468 (delta=0.0034), global BA at best=0.9036, status=partial
- caregiver/conduct site=CUNY: BA 0.9028 -> 0.9028 (delta=0.0000), global BA at best=0.9493, status=no
- caregiver/elimination source_mix=mid_gap: BA 0.6964 -> 0.6964 (delta=0.0000), global BA at best=0.8109, status=no
- psychologist/conduct site=CUNY: BA 0.9306 -> 0.9306 (delta=0.0000), global BA at best=0.9514, status=no

## Dominant risk signals in fragile slices
- Negative coverage gap and positive source_mix_gap recurrently co-occur with BA drops.
