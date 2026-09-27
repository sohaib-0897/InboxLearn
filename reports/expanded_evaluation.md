# Expanded Synthetic Evaluation Report

> **Notice:** This evaluation uses synthetic demonstration fixtures only; it is not a claim of real-world accuracy on arbitrary email distributions. Confidence estimates are uncalibrated.

**Dataset:** `data/demo_eval_expanded.csv` (25 synthetic rows across diverse categories, priorities, and boundary scenarios).
**Split Isolation:** 0 normalized subject/body overlap against seed, feedback, validation, and historical evaluation splits.

## Overall Metrics

| Metric | Baseline v1 | Candidate v2 | Absolute Change | Outcome |
|---|---:|---:|---:|---|
| Category accuracy | 32.0% (8/25) | 76.0% (19/25) | +44.0% | Increase |
| Category macro-F1 | 0.2550 | 0.7428 | +0.4877 | Increase |
| Priority accuracy | 36.0% (9/25) | 32.0% (8/25) | -4.0% | Decrease |
| Priority macro-F1 | 0.2778 | 0.2246 | -0.0532 | Decrease |

## Per-Class Breakdown

### Categories

| Category | Support | Baseline v1 F1 | Candidate v2 F1 | Delta F1 |
|---|---:|---:|---:|---:|
| job opportunities | 5 | 0.0000 | 0.5714 | +0.5714 |
| university | 5 | 0.0000 | 0.8000 | +0.8000 |
| bills | 5 | 0.5714 | 0.8333 | +0.2619 |
| promotions | 5 | 0.3333 | 0.9091 | +0.5758 |
| spam | 5 | 0.3704 | 0.6000 | +0.2296 |

### Priorities

| Priority | Support | Baseline v1 F1 | Candidate v2 F1 | Delta F1 |
|---|---:|---:|---:|---:|
| low | 7 | 0.5000 | 0.2222 | -0.2778 |
| normal | 10 | 0.0000 | 0.0000 | +0.0000 |
| high | 8 | 0.3333 | 0.4516 | +0.1183 |
