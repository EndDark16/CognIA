Healthy Brain Network (HBN) synthetic phenotypic package - Release 11 focused subset

What this is
- A schema-faithful synthetic dataset package grounded in public HBN documentation for the following disorder families:
  1) Trastornos de conducta / disruptive-impulse-control-conduct disorders
  2) TDAH
  3) Trastornos de eliminación
  4) Trastornos de ansiedad
  5) Depresión
- It preserves public HBN table names where they are documented (for example Diagnosis_ClinicianConsensus, Diagnosis_KSADS_T/P/D).
- It uses the public age windows, item counts, and response ranges that are documented on the HBN portal or on public instrument pages.
- All values are synthetic. No row corresponds to any real HBN participant.

Important honesty note
- This package is intentionally close to HBN's public schema, but it is not a claim of byte-for-byte identity with the hidden/original HBN data dictionaries.
- Exact original HBN item-level variable names are not publicly exposed for every instrument without downloading the official dictionaries / using the access portals.
- Where the exact public variable names were not accessible, standardized item names were used (for example SWAN_01..SWAN_18).
- For Diagnosis_KSADS_T/P/D, exact hidden item columns were not publicly visible, so synthetic proxy summary columns were created.
- For some instruments (especially ICUT and some legacy measures), public HBN pages describe the instrument and age range but not the full public coding sheet; these were simulated using literature-standard conventions and clearly marked in the data dictionary.

How it was made
- Participant count anchored to the public Release 11 phenotypic total of 4,867.
- Age range anchored to the public HBN range 5-22 years.
- Sex distribution anchored to the public fact sheet counts (with 4 synthetic Unknown values because the published male/female totals sum to 4,863 rather than 4,867).
- Diagnostic generation was calibrated qualitatively to public HBN patterns: ADHD and anxiety dominate, multi-diagnosis is allowed, and a no-diagnosis subgroup is retained.
- Item responses were simulated with correlated latent traits so that ADHD, anxiety/depression, conduct/externalizing, and elimination-related variation show realistic comorbidity.

Files included
- One Excel workbook with all tables
- One zip archive with the same tables as CSV files

Not for clinical use.