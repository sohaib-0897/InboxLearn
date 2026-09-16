# InboxLearn — portfolio evidence

Local email triage with a Newsprint Streamlit interface, separate incremental classifiers for category and priority, SQLite feedback history, immutable candidate snapshots and reversible activation after evaluation. No paid API or Gmail dependency.

## CV bullets

- Built a local Python/Streamlit email triage agent using SQLite, HashingVectorizer and separate incremental SGD classifiers, with fast human review, read-only prediction comparisons, evaluation-gated candidate activation, model lineage and rollback.
- Verified learning on 5 synthetic feedback emails and 10 disjoint held-out examples: category accuracy rose from 50% to 90% and priority accuracy from 30% to 80%; confirmed exact prediction/confidence restoration on 15 rollback probes.

## Evidence and scope

[Measured results and method](reports/learning.md) · [Full-precision JSON](reports/learning.json) · [Reproduction script](scripts/experiment.py) · [Real app screenshots](docs/screenshots/README.md)

These numerical results describe only the supplied synthetic demonstration fixtures. They are not real-world accuracy claims or a human-subject evaluation. Labels were pre-authored and replayed through the application's human-feedback API. “Normal” priority remained 0/2 correct, and one university email remained misclassified. Confidence is uncalibrated and all next actions are suggestions only.

The verification fixed a feedback-content join defect and added tests for actual content-based updates and pre-training split isolation. No fixture or model hyperparameter was changed to improve held-out scores. Repeatedly inspected test scores are not an unbiased final benchmark. Independent real-world evaluation, other browsers and screen-reader testing remain future work.

## Walkthrough

Classify → correct with **Save and next** → **Prepare candidate** → inspect **Inbox prediction changes** → evaluate → activate → roll back. Preparing a model leaves the active version in use and repeated requests reuse the same candidate. The service requires a persisted evaluation matching the current held-out dataset before candidate activation; regressions remain visible and the user decides whether to proceed.

The fixed experiment changes category or priority labels on **4 of 5 inbox messages**. Those messages are marked as training members, so that agreement is not held-out accuracy. The original inbox predictions remain intact, candidate snapshots do not absorb later corrections, and rollback restores the earlier model. Real Chrome captures show the entire workflow independently on desktop and mobile viewports.
