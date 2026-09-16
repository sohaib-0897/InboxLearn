# Synthetic learning experiment

Synthetic demonstration data; not a real-world accuracy estimate.

Fixed protocol: 15 synthetic seed examples → classify 5 separate feedback emails → replay their pre-authored labels through the human-feedback service → prepare an inactive candidate → inspect inbox prediction changes → evaluate on the same 10 held-out examples → explicitly activate → roll back to v1.

The 5 validation examples were checked for split isolation but not used for tuning. No thresholds, model parameters or examples were selected in response to held-out scores.

| Metric | Baseline v1 | Updated v2 | Absolute change (v2 − v1) | Outcome |
|---|---:|---:|---:|---|
| Category accuracy | 0.5000 | 0.9000 | +0.4000 | Increase |
| Category macro-F1 | 0.4222 | 0.8933 | +0.4711 | Increase |
| Priority accuracy | 0.3000 | 0.8000 | +0.5000 | Increase |
| Priority macro-F1 | 0.2222 | 0.6190 | +0.3968 | Increase |

Values are on a 0–1 scale; changes are signed score-point differences, not relative percentages.

Did not improve: none of the four metrics in this particular synthetic run.

Remaining class-level errors:

- Category / university: 1/2 correct after training (baseline 0/2).
- Priority / normal: 0/2 correct after training (baseline 0/2).

## What changed

Candidate preparation left active predictions unchanged and repeated preparation returned the same candidate. Activation was rejected before evaluation. The read-only inbox preview found 4 of 5 messages with changed category or priority labels; these feedback training members are not held-out accuracy evidence. The candidate was evaluated before explicit activation.

Both classifiers consumed exactly 5 new human-label fixtures through partial_fit; their coefficients changed. Feedback email content is joined to its latest saved labels. Earlier verification found that this join was missing; a regression test now checks that service updates equal updates made directly with the actual email text. Missing text fails early, and overlap with the held-out or validation splits is rejected before fitting.

Only the new v2 model changed. Original predictions, the v1 snapshot, all fixture files, model hyperparameters and thresholds stayed fixed. No prediction was reused as a training label. Repeated training was a no-op. The separate validation set was not tuned in this experiment.

Rollback restored v1's exact labels AND confidence estimates on 15 probes (5 feedback + 10 held-out), including after reopening SQLite. The stored model bytes matched exactly. Human feedback remained available. All six split-pair overlap checks returned zero.

## Limitations

These small, English-language, synthetic fixtures demonstrate mechanics, not real-world generalization. The replayed labels are demonstration ground truth, not newly collected human annotations. Confidence is uncalibrated. Test scores have been repeatedly inspected during development and are not an unbiased final benchmark; use new independent data for that purpose. Feedback can cause regressions. Actions are suggestions only; no sending, deletion, payments or integrations. Hash normalization detects exact normalized duplicates, not semantic paraphrases. Serialized model compatibility depends on the Python/scikit-learn environment; old user versions are not rewritten by this verification.

## Reproduce

```powershell
.\.venv\Scripts\python.exe scripts\experiment.py
```

This command creates and removes its own temporary database under runtime/experiments, ignores INBOXLEARN_DB, and writes only reports/learning.json and reports/learning.md. Run with the dependency versions recorded in the JSON for the closest numerical reproduction. JSON includes full precision metrics, confusion matrices, fixture and source hashes, class counts, model changes and per-probe rollback evidence.
