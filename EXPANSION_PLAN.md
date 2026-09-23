InboxLearn Expansion Roadmap

Next release: v2 — Real Email Import, Read-Only Gmail & Reliable Review
Status: Proposed implementation plan, not a completion report
Product: Human-in-the-loop email triage application
Principle: Improve everyday usefulness while keeping the system small, measurable, and maintainable.

1. Goal and scope

Extend InboxLearn so users can import actual email files or connect one Gmail account locally, review predictions efficiently, and learn from confirmed corrections. Preserve the Newsprint interface and the existing Python, Streamlit, SQLite, and scikit-learn architecture.

The next release must complete this workflow:

Import files or sync Gmail → inspect → classify → confirm/correct → train candidate → validate → activate or reject → roll back.

A successful v2 is a reliable, demonstrable application. It does not need a desktop wrapper, local LLM, autonomous mailbox management, or a new frontend.

2. Establish the baseline before editing

Read AGENTS.md and inspect the repository, migrations, tests, deployment configuration, and existing experiment reports. Treat previous completion reports as claims to verify.

Previously reported capabilities include CSV import, category/priority classification, persisted corrections, incremental training, model versions, rollback, evaluation, and the Newsprint UI. Verify which are actually implemented before relying on them. Inactive candidates, activation gates, and previews must not be described as existing guarantees without code and runtime evidence.

Record baseline test results and confirm the application starts. Preserve user data and unrelated changes. Use temporary databases for experiments and tests.

Historical results on ten synthetic test examples demonstrate one learning experiment, not real-world reliability. Retain those results with their original sample counts and limitations; never replace them silently with a more favorable run.

3. Non-negotiable behavior

Train only on seed labels and explicitly human-confirmed feedback, never automatic predictions.

Preserve original predictions, producing model version, corrections, and training lineage.

Prevent duplicate feedback consumption within a lineage; revised labels must not silently accumulate contradictory training updates.

Train inactive candidates. Keep activation a distinct, deliberate operation.

Use validation data for candidate selection and activation policy. Reserve separate final test data for reporting.

Keep immutable model versions and restore the full inference configuration on rollback, including preprocessing and any calibration.

Show measured regressions and missing results honestly.

Keep CSV import/export and existing workflows working.

Never send, delete, move, or modify external mail in v2.

Do not claim local privacy for a hosted application: server-hosted Streamlit processes uploaded content on its server.

4. Phase A — Real email import

Deliverables

Support individual .eml files and bounded .mbox archives alongside CSV. Use Python's standard email and mailbox facilities where appropriate. Outlook .msg, live IMAP, and attachment content extraction are out of scope.

Build one normalized email representation shared by all importers:

Source type and import batch identifier

Decoded subject, sender, recipients, and message date where available

Message-ID, In-Reply-To, and References where available

Plain reading text and separately derived classification text

Content fingerprint, parser warnings, and preprocessing version

Missing or invalid headers must not crash the import. Preserve unknown dates rather than inventing timestamps.

Parsing requirements

Handle multipart alternatives, encoded headers, quoted-printable/base64 bodies, Unicode, and unknown or malformed charsets.

Prefer a usable plain-text body; otherwise convert HTML to readable text.

Display email content as escaped text. Never execute embedded HTML or fetch remote images, styles, links, or tracking pixels.

Treat HTML parsing and HTML sanitization as different operations. A parser alone is not a safe HTML renderer.

Exclude attachments from classification. Bound MIME nesting and decoded content size; report skipped or oversized content.

Make quote/signature removal conservative and reversible. Keep original reading text and expose the derived text for debugging.

Parse threading headers as metadata; defer a complete thread viewer.

Treat imported authentication headers as untrusted claims, not independently verified SPF/DKIM/DMARC results.

Import integrity

Set documented limits for file bytes, message count, message size, and MIME processing. Process archives incrementally rather than loading all decoded messages at once.

Use a normalized-content fingerprint for duplicate detection. Message-ID alone is insufficient because it may be missing, reused, or malformed. Retain enough provenance to explain why an item was skipped.

Present imported, duplicate, rejected, and warning counts. Define partial-import behavior clearly and make retries idempotent. Clean up temporary files on success and failure.

Acceptance criteria

Plain-text, HTML-only, multipart, encoded-header, malformed-charset, missing-header, and attachment-bearing fixtures have expected outputs.

Reimporting the same EML/MBOX creates no duplicate emails or feedback.

A malformed message produces an actionable warning without silently discarding other valid messages.

Oversized files and deeply nested MIME are bounded safely.

Imported mail enters the same classification, review, training, and evaluation paths as CSV.

No external content requests occur while parsing or viewing messages.

5. Phase B — Reliable, faster review

Preserve the Newsprint design. Improve the current UI rather than replacing it.

Deliverables

A prominent Save and next action that commits feedback before advancing.

Filters for category, priority, review state, and import batch.

Stable message selection across filtering and Streamlit reruns.

Clear separation of original prediction, latest confirmed labels, and optional current-model preview.

Batch confirmation for explicitly selected messages, with a preview of affected items and labels.

Clear saved, unsaved, training-eligible, and already-consumed feedback states.

Visible explanations for why an email needs review.

Keyboard shortcuts are optional. Add them only if accessible and maintainable with the installed Streamlit stack. They must not trigger while typing, interfere with native widgets, or cause double submissions. Visible controls remain the primary supported workflow.

Acceptance criteria

Saving a correction twice does not create duplicate training input.

Revising a correction follows the established rebuild/lineage policy.

Batch actions affect only the previewed selection, including after filtering.

Failed saves retain the current message and entered correction.

Empty queues, deleted selections, and concurrent state changes fail clearly.

Desktop/mobile workflows retain readable layouts, keyboard focus, and usable controls.

6. Phase C — Evidence and learning quality

Data protocol

Write category and priority labeling guidelines, including ambiguous cases and the meaning of normal priority. Keep category and urgency distinct: a bill is not automatically high priority.

Separate seed/training data, feedback, development validation, and final test data. Split related templates, threads, and scenario families together to reduce leakage. Check exact and normalized overlap and review likely near-duplicates.

Previously inspected test sets become development evidence when used to guide changes. Do not present repeated tuning against them as fresh final evaluation.

Use a reproducible, more varied synthetic dataset initially. Label it synthetic throughout. Real-world claims require a separately documented, permitted, appropriately labeled real-email evaluation; do not collect private mail merely to expand the benchmark.

Evaluation

Compare the initial baseline and feedback-updated candidate on identical examples. Report:

Sample counts and class support

Accuracy and macro-F1 for category and priority

Per-class precision, recall, and F1

Confusion matrices and regressions

Review-queue rate and accuracy among automatically classified examples

Dataset, preprocessing, model, and experiment identifiers

Pay particular attention to normal-priority failures. Diagnose data coverage, label ambiguity, preprocessing, and learning behavior before adding model complexity.

Activation and rollback

Define candidate gates on validation data with explicit minimum support, per-class checks, and regression tolerances. Do not demand improvement in every metric or promise that additional feedback always helps.

Insufficient evidence must produce a clear status rather than an automatic quality claim. An explicit override, if supported, must be recorded as such.

Run the final test after freezing the approach. If its results motivate further development, record that decision and treat the set as inspected for future claims.

Verify rollback restores predictions on a defined probe set in the supported environment. Claim bit-for-bit equality only where actually tested; do not imply cross-platform or cross-version guarantees.

7. Phase D — Direct Gmail connectivity (read-only)

Release boundary

Implement Gmail API integration after Phase A establishes the shared parser and normalizer. The initial supported deployment is a single-user InboxLearn instance running on the same computer as the user's browser, connected to one Gmail account. Keep CSV, EML, and MBOX fully usable without Google credentials or network access.

Use the Gmail API rather than IMAP for this integration. This phase imports messages only: no sending, drafts, archiving, labels, mark-as-read, trash, or deletion. Local review status must never change Gmail state.

User workflow

Connect Gmail → Google consent → choose import window/limit → Sync → classify → review/correct → Disconnect.

Show the connected account, read-only access, selected import window, last successful sync, imported/skipped/failed counts, and any incomplete run. Use explicit Connect, Sync, Cancel, and Disconnect controls. Streamlit reruns must not trigger authorization or synchronization automatically.

Default to a bounded recent window, such as the last 30 days with a 100-message cap. Explain that these are import filters, not OAuth permission restrictions: the granted read-only scope can access the mailbox more broadly. Do not label the import a complete mailbox backup.

OAuth and credentials

Enable the Gmail API in a user-owned Google Cloud project; configure the consent screen, permitted test users where applicable, and a Desktop OAuth client for the local release.

Request only https://www.googleapis.com/auth/gmail.readonly for mailbox access. Do not request gmail.modify, gmail.send, or full-mail scope.

Use a maintained Google OAuth library, the system browser, authorization-code flow with PKCE, state validation, and a short-lived loopback callback bound only to loopback. Reject mismatched, expired, or replayed callbacks.

Never request the user's Google password, use an embedded login browser, or use deprecated copy/paste authorization-code flows.

Store refresh tokens in an OS-backed credential store. Do not silently fall back to plaintext token files; if secure persistence is unavailable, offer an explicit session-only connection or report the setup requirement.

Keep tokens and OAuth configuration out of source control, ZIPs, logs, screenshots, exports, query strings, and shared Streamlit caches. A desktop client secret is not a substitute for protecting user tokens.

Handle access-token refresh, missing refresh tokens, consent denial, revoked grants, and reauthentication explicitly. Do not loop indefinitely on authentication failures.

Document the external setup the user must provide. If OAuth credentials or a test account are unavailable, complete offline connector tests and mark live authorization/sync NOT_VERIFIED. Do not fabricate a successful Gmail connection.

Fetching, parsing, and deduplication

Use paginated users.messages.list and bounded users.messages.get requests through an adapter that calls the existing normalization/import service.

Prefer structured message payloads and skip attachment retrieval. Fetch a separately stored body part only when it is needed for message text and within byte limits; do not download every attachment.

Preserve Gmail message ID and thread ID separately from RFC Message-ID. Use an account-scoped unique key for each Gmail message.

Repeated sync must not duplicate messages, original predictions, or feedback. Link duplicate content across import sources to provenance records without losing distinct Gmail identifiers.

Keep pagination/run state and counts durable enough for interrupted runs to resume safely. Prevent concurrent syncs for the same connection.

Start with user-triggered bounded sync and idempotent re-fetching. Defer history-based incremental sync and push notifications. Do not claim that a date filter captures all mailbox changes.

Apply explicit request timeouts, bounded retries with backoff for transient failures, rate-limit handling, and clear cancellation. Distinguish quota failures, expired authentication, missing messages, and parser errors.

Never execute email HTML or fetch external resources while viewing Gmail messages. The network exception is authorized Google API/OAuth traffic, not arbitrary email links or remote images.

Disconnect and data ownership

Disconnect stops new and in-flight commits for that connection, attempts grant revocation, and removes locally stored tokens and connection caches. Report revocation failure honestly and provide instructions for revoking access in Google Account settings.

Disconnect is not deletion of imported content. Offer a separate, clearly scoped local-data deletion operation and describe exactly what remains. If feedback has trained model versions, do not claim complete removal of learned influence merely by deleting email rows. Either remove account-derived models and rebuild from permitted remaining data, or disclose the retained artifacts and provide a full local reset.

Do not pool Gmail content or feedback across users or publish it as training/benchmark data. Review applicable Google user-data and Limited Use requirements before distribution; importing mail is not permission for unrelated model training.

Hosted Gmail is a later deployment milestone

Disable the local Desktop OAuth connector on the public hosted demo. A localhost callback on a remote server does not connect the visitor's browser to that server correctly.

Hosted support requires a Web OAuth client, registered HTTPS callback, authenticated application sessions, server-side token protection, and tested per-user isolation of emails, credentials, models, feedback, sync state, caches, and exports. A connection to Google is not by itself a complete application authorization system.

Gmail read-only is a restricted scope. Review current Google verification rules and any applicable personal/testing exceptions before rollout. Public distribution may require restricted-scope verification; server handling of restricted data can trigger a security assessment. Do not promise that a hosted launch is free of review, cost, or approval dependencies.

State accurately that hosted processing happens on the server; local processing happens on the user's computer but still communicates with Google for OAuth and mail retrieval.

Acceptance criteria

Consent denial, callback mismatch/replay, expiration, refresh failure, and revocation have clear tested outcomes.

Repeating a sync or rerunning the Streamlit page creates no duplicate imports or feedback.

Pagination, message caps, cancellation, retry exhaustion, deleted messages, and malformed MIME are tested.

Gmail-imported emails follow the same correction, candidate training, validation, and rollback paths as uploaded emails.

Tests assert that no Gmail write methods are called and local review does not change remote labels/read state.

Disconnect prevents further imports and clears credentials; retention/deletion behavior matches the UI description.

Local OAuth behavior is exercised with an explicitly authorized test mailbox when credentials are available; only sanitized fixtures enter the repository.

Public-demo configuration keeps Gmail disabled until hosted requirements are met.

8. Optional v2 feature — Calendar file export

Add only after the core phases pass.

Extract a proposed date/deadline and show its source phrase. Let the user edit and confirm the title, date, time, and timezone before generating a downloadable .ics file.

Resolve relative dates against a documented reference date, preferably the message date when reliable.

Leave ambiguous dates unresolved for user input.

Preserve all-day dates as dates; do not silently convert them into midnight UTC events.

Use a maintained iCalendar serializer and test escaping, timezone behavior, and file validity.

Download only: no invitations, calendar writes, or external calls.

9. Storage, migrations, and deployment

Derive migrations from the actual schema rather than applying a speculative SQL block.

Use versioned, transactional migrations tested against an existing populated database.

Preserve labels, predictions, model versions, feedback, and lineage.

Add import metadata and indexes only where the implemented workflow requires them.

Verify foreign-key enforcement and concurrency behavior; WAL alone does not prevent logical races.

Avoid retaining raw archives or attachments by default. Document retention and deletion behavior.

Never load model artifacts or databases supplied by untrusted users.

For hosted demos, use non-sensitive sample content. Before supporting private uploads on a public deployment, verify isolation of emails, feedback, model state, caches, and exports between users. A shared SQLite database is not automatically a multi-user security boundary. If isolation is absent, restrict uploads to a private/local deployment or implement isolated disposable demo workspaces.

10. Deferred expansion, with entry conditions

These features are options, not requirements for completing v2.

Feature

Entry condition and constraints

Other-provider IMAP/OAuth

Stable file import plus an account/credential model; test cursor persistence, UIDVALIDITY, deduplication, reconnects, and provider behavior. Never mark messages read during ingestion.

Gmail history sync / push

A measured need beyond bounded manual import. Persist history cursors safely; expired history IDs require a recovery sync. Pub/Sub and background jobs are separate deployment work.

Semantic embeddings

Show a baseline limitation on representative validation data. Compare quality, latency, memory, and package size on actual hardware. Preserve an incremental learning path.

Probability calibration

Sufficient independent representative labeled data; fit calibration separately from classifier training and bind it to the exact model version. Reassess after each model update.

Conformal prediction

Adequate separate calibration data and a defensible exchangeability assumption. Explain marginal coverage, monitor set size, and route empty or multi-label sets to review. Singleton sets do not imply per-email guaranteed correctness.

Custom categories/multi-label

Defined taxonomy versioning, label migration, evaluation, and retraining strategy. New SGD classes are not simply a database insertion.

Safer model persistence

Assess skops.io or a carefully specified state format for the actual estimator. Verify continuation of training and rollback. ONNX inference export is not a complete training checkpoint; SafeTensors is not a drop-in sklearn serializer.

Local LLM drafting

Demonstrated benefit and explicit resource requirements. Treat email text as untrusted input; generate drafts only, with no autonomous tools or sending.

External actions

Separate authorization, durable idempotency keys, remote receipt reconciliation, and audit history. Undo is best-effort where provider state permits, not a universal guarantee.

FastAPI/background worker

A concrete need for background sync or multiple clients. Extract existing services rather than duplicating business logic.

Desktop app/encrypted storage

Established usage need and a supported installation/update/key-management plan. Encryption at rest does not ensure complete security.

Calibration improves estimated reliability; it does not produce infallible “true probabilities.” Isotonic calibration is especially prone to overfitting with small samples. Corrected uncertain emails are a biased sample and must not be treated as a representative calibration or overall accuracy dataset without justification.

Checksums detect corruption only relative to a trusted digest; they do not establish authenticity if an attacker can replace both artifact and hash. Performance figures remain NOT_MEASURED until benchmarked.

11. Release verification and stopping rule

Run meaningful tests through production services, not only mocked helpers:

Existing regression suite and isolated dependency check.

Parser/import fixtures, limits, retry behavior, and migration from an existing database.

Upload → review → revised correction → train candidate → validate → activate → rollback → train again.

Streamlit AppTest and browser checks for the changed desktop/mobile workflows where tools are available.

Reproducible experiment in a temporary workspace without modifying user data.

Gmail connector error-path tests and an authorized live read-only sync where credentials are available.

Clean startup from packaged source using documented commands, including operation with Gmail disabled.

Update README with supported formats, limits, privacy/deployment boundaries, data limitations, and setup instructions. Save the measured experiment report, real screenshots, and a short demo walkthrough. Package source and safe fixtures, excluding private emails, runtime databases, model binaries, credentials, caches, and virtual environments.

Report each planned capability as VERIFIED, IMPLEMENTED_NOT_VERIFIED, DEFERRED, or BLOCKED, with supporting evidence. Do not label the product production-ready solely because tests pass.

Stop expanding v2 when real-email import, local read-only Gmail connectivity, reliable review, learning/version integrity, and reproducible evaluation pass. If live Gmail verification is blocked by missing credentials, release the file-import workflow with Gmail explicitly marked unverified rather than declaring that phase complete. Further features require a demonstrated user need or measured limitation.

References

Gmail scopes and restricted-data requirements: https://developers.google.com/workspace/gmail/api/auth/scopes

Google OAuth for installed applications: https://developers.google.com/identity/protocols/oauth2/native-app

Restricted-scope verification: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification

Gmail synchronization: https://developers.google.com/workspace/gmail/api/guides/sync

Google API Services User Data Policy: https://developers.google.com/terms/api-services-user-data-policy

scikit-learn probability calibration: https://scikit-learn.org/stable/modules/calibration.html

scikit-learn model persistence: https://scikit-learn.org/stable/model_persistence.html

MAPIE conformal prediction: https://mapie.readthedocs.io/en/stable/content/conformal-prediction/

These references clarify design constraints; they do not verify InboxLearn's implementation.