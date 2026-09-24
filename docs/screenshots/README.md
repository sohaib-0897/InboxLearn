# Real application captures

Captured from InboxLearn's actual Streamlit UI in Chrome using only the shipped synthetic demo files. These are unedited browser screenshots, not generated mockups. The capture script starts an isolated database for each viewport and completes the native upload, save-and-next, follow-up scheduling, completion, cancellation, reopening, candidate preparation, prediction preview, evaluation, activation and rollback workflow on both.

The five labels in `data/demo_feedback.csv` are replayed through the review forms. Scores and preview results are checked against `reports/learning.json` before the images are copied here. `capture.json` records browser version, viewports, startup health, verification outcomes and artifact hashes. Captures are illustrative UI views of the synthetic experiment, not evidence of real-world accuracy. Mobile means a Chrome viewport at 390×844; a physical phone was not tested.

| Desktop / mobile capture | View |
|---|---|
| [Landing page](desktop-landing.png) / [mobile](mobile-landing.png) | Default app entry point, with a simulated preview and links into the real workspace |
| [Today](desktop-today.png) / [mobile](mobile-today.png) | Local follow-ups grouped by deadline |
| [Empty Today](desktop-today-empty.png) / [mobile](mobile-today-empty.png) | Import instructions and demonstration entry point |
| [Inbox](desktop-inbox.png) / [mobile](mobile-inbox.png) | Imported demo emails with effective labels and original prediction details |
| [Review](desktop-review.png) / [mobile](mobile-review.png) | Subject selectors, confidence sorting and save-and-next |
| [Candidate](desktop-candidate.png) / [mobile](mobile-candidate.png) | Inactive candidate; activation disabled pending evaluation |
| [Prediction changes](desktop-prediction-changes.png) / [mobile](mobile-prediction-changes.png) | Before/after preview with training-membership caveat |
| [Evaluation](desktop-evaluation.png) / [mobile](mobile-evaluation.png) | Measured baseline/updated comparison |
| [Confusion matrices](desktop-matrices.png) / [mobile](mobile-matrices.png) | Category and priority error distributions |
| [Versions](desktop-versions.png) / [mobile](mobile-versions.png) | Model ledger after rollback and reactivation |

Reproduce from the project root after running the experiment:

```powershell
.\.venv\Scripts\python.exe -m pip install playwright
.\.venv\Scripts\python.exe scripts\browser_qa.py --portfolio
```

Chrome must be installed. Screenshots, temporary runtime databases and logs are initially written under `runtime/newsprint-qa/`; only the listed images and public capture evidence are copied into this folder. Only this curated folder is included in the portfolio archive.
