# Questionnaire API Contract (simulated)

POST /api/questionnaire/submit
- payload follows questionnaire_input_schema.json
- response follows questionnaire_output_schema.json

Expected backend behavior:
1. Validate questionnaire_item_id against questionnaire_items_registry.csv
2. Validate response value against response_type + allowed_values
3. Map response to normative parameter using questionnaire_to_normative_mapping.csv
4. Return coverage deltas and warnings when critical criteria remain missing
