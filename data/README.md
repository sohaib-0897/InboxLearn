# Demonstration data

All CSVs in this folder are synthetic demonstration data and use reserved `example.test` addresses:

- `demo_seed.csv`: reproducible labelled seed used to create the baseline model.
- `demo_validation.csv`: labelled validation data reserved for threshold or model tuning.
- `demo_feedback.csv`: example human-confirmed corrections; it is reference material and is not silently ingested as user feedback.
- `demo_eval.csv`: separate labelled held-out data used for baseline/version comparisons.

Normalized content overlap between training inputs and held-out evaluation data is checked before evaluation.
