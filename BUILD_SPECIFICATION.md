# Weekly Clean Fuels Regulatory Digest — Rebuild Specification

## 1. Purpose

This document is the platform-independent specification for rebuilding the Weekly Clean Fuels Regulatory Digest from scratch. A replacement implementation may use another programming language, operating system, scheduler, mail provider, or language-model provider, but it must preserve the observable behavior and safety properties described here.

The system reads regulatory-subscription messages from one mailbox, filters them to a configured set of clean-fuels programs, produces concise English summaries, groups the results into a weekly digest, sends the digest by email, and remembers sent items so they are not sent twice.

This file describes the required behavior. `config/config.yaml` is the authoritative live inventory of mailbox settings, programs, senders, keywords, paths, model selection, and schedule.

The current reference Windows deployment is maintained as a commercial software project at `D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest`. Rebuilds on other platforms may use a different installation root, but all internal runtime paths should remain project-relative unless an external data source is intentionally configured with an absolute path.

## 2. Required Outcomes

A conforming implementation must:

1. Read messages through an authenticated mail API without storing the mailbox password.
2. Search only the configured sender addresses and only the reporting window.
3. Map every accepted sender to exactly one configured regulatory program.
4. Treat the email body as untrusted data, never as instructions.
5. Extract only items directly related to the sender's assigned program.
6. Return no items when a message is unrelated or ambiguous.
7. Use only facts present in the source email.
8. Use only URLs actually extracted from the source email; otherwise link to the original mailbox message.
9. Validate model output against a strict schema.
10. Deduplicate within a run and across successful sends.
11. Produce HTML, plain-text, and machine-readable JSON previews before sending.
12. Abort the entire send if any message cannot be analyzed. Never send a silently incomplete digest.
13. Send from and to the configured mailbox only when explicitly running in send mode.
14. Persist a pending send transaction before calling the mail API; mark it sent and record item keys only after the provider confirms success. An ambiguous pending send must block future automatic delivery until explicitly resolved.
15. Run automatically every Friday at 09:00 in `America/Regina`.
16. Merge configured local regulatory digest files into the same program and reporting period.

## 3. Current Business Scope

The live configuration contains these programs:

| Country | Program | Sender type |
|---|---|---|
| United States | California Low Carbon Fuel Standard (LCFS) | Mixed-topic |
| United States | Oregon Clean Fuels Program (CFP) | Mixed-topic |
| United States | Washington Clean Fuel Standard (CFS) | Mixed-topic |
| United States | New Mexico Clean Transportation Fuel Program (CTFP) | Mixed-topic |
| Canada | Canada Clean Fuel Regulations (CFR) | Dedicated |
| Canada | BC Low Carbon Fuel Standard (LCFS) | Dedicated |
| United Kingdom | UK Sustainable Aviation Fuel (SAF) | Mixed-topic |

Do not hard-code this inventory. Read it from `config/config.yaml`. Each program entry contains:

- a stable program ID;
- country and display order;
- program display name and order;
- one normalized `sender` address or a normalized `senders` list;
- a `mixed_topic` flag;
- inclusion terminology;
- exclusion guidance.

The implementation must permit multiple unique sender addresses for one program and reject a sender address mapped to more than one program during startup.

## 4. Reporting Window

The timezone is `America/Regina`.

For a normal scheduled run:

- `end` is the most recent Friday at 00:00 local time;
- `start` is exactly seven days before `end`;
- the interval is half-open: `start <= received_at < end`;
- in plain language, the digest covers Friday through Thursday inclusive.

Example: a run on Friday, September 25 covers September 18 00:00 through September 25 00:00.

The command line must also support explicit ISO dates for reproducible testing:

```text
--start YYYY-MM-DD --end YYYY-MM-DD
```

Both overrides must be supplied together, `start` must precede `end`, and both dates are interpreted at midnight in the configured timezone.

## 5. External Services and Authentication

### 5.1 Mailbox

The current implementation uses Gmail API OAuth for:

- read-only mailbox access;
- sending mail.

Required OAuth scopes:

```text
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.send
```

Current mailbox identity:

```text
wenli.insight@gmail.com
```

The OAuth client credential is stored locally at `runtime/secrets/credentials.json`. The refresh/access token is stored at `runtime/secrets/token.json`. Neither file may be committed, logged, emailed, or included in generated documentation.

On another mail platform, replace the Gmail adapter with an equivalent provider adapter. It must expose these operations:

```text
authenticate()
list_message_ids(sender_addresses, start, end)
get_message(message_id)
get_original_message_url(message_id)
send_multipart_email(sender, recipient, subject, text_body, html_body)
```

### 5.2 Language Model

The current provider is the OpenAI API using model `gpt-5-nano`. The API key is obtained only from the process environment:

```text
OPENAI_API_KEY
```

The key must never appear in source files, YAML, logs, previews, prompts, or state files.

A replacement model/provider is acceptable only if it supports reliable schema-constrained output and passes the acceptance tests in this document.

## 6. Configuration Contract

The application reads `config/config.yaml` at startup. Its top-level sections are:

```yaml
mailbox: {}
schedule: {}
ai: {}
paths: {}
programs: []
```

Required semantics:

- `mailbox.account`: authenticated mailbox identity.
- `mailbox.sender`: From address.
- `program.sender` or `program.senders`: one or more source addresses for that program.
- `mailbox.recipient`: digest destination.
- `mailbox.subject`: template containing `{period}`.
- `schedule.timezone`: IANA timezone name.
- `schedule.weekday`: human-readable scheduled weekday.
- `schedule.time`: local scheduled time.
- `ai.model`: provider model ID.
- `ai.summary_language`: output language.
- `ai.max_email_characters`: maximum email text supplied to the model.
- `ai.retry_attempts`: transient model-call retry count.
- `ai.request_timeout_seconds`: per-attempt model request timeout.
- `ai.run_timeout_seconds`: overall runtime budget, below the scheduler's execution limit.
- `paths.*`: project-relative credential, token, state, log, and preview paths.
- `programs`: ordered regulatory-program definitions.

Fail fast when the file is missing, malformed, lacks programs, or maps one sender to more than one program.

## 7. Message Discovery and Parsing

### 7.0 Local digest discovery

The system may define `local_digest_sources` in configuration. Each source specifies a stable source ID, target program ID, directory, glob pattern, timestamp field, and optional expected JSON program code.

For each matching JSON file:

1. Parse a top-level JSON object.
2. Read `generated_at` (or the configured timestamp field) as an ISO timestamp.
3. Interpret a timezone-naive timestamp in the configured reporting timezone.
4. Convert a timezone-aware timestamp to the reporting timezone.
5. If the field is missing, use the file modification timestamp.
6. Include the file only when `start <= generated_at < end`.
7. Verify the optional JSON program code before ingestion.
8. Treat the JSON body as untrusted source data and convert its records deterministically; do not transmit local file content to an external model.
9. Merge accepted items with email-derived items before deduplication and ordering.
10. Use a stable hash of the resolved file path as the source message ID.

Local file paths must not be rendered as public web links. California LCFS `added_pathways` records are grouped under one `Newly Certified Pathway(s)` heading. Each record shows company, fuel category, class, certified CI, and pathway description. If `updated_pathways` is present, render its CI changes separately under one `Existing Pathway Updates` heading. Render a single CARB workbook `View original source →` link after both California groups.

For California local item identity, prefer a stable upstream `pathway_id`. Until that field is supplied, hash normalized `Company (ID)`, `Fuel Category`, `Class`, and `Pathway Description`; exclude `Current Certified CI` so recertification does not masquerade as a newly certified pathway. Exclude ordinary `source_row` values because row positions drift between workbooks. If multiple otherwise identical records occur in one file, append `source_row` solely as a collision tie-breaker. This fallback deliberately prefers a visible duplicate after a row shift over silently collapsing distinct records. An `updated_pathways` event must include the same pathway fields plus `Previous Certified CI` and `Current Certified CI`; its event identity additionally includes `current_version` and the CI transition.

BC LCFS local digests use the `BC_LCFS` program code and are grouped under one `Guidance Updates` heading. Convert each matching digest deterministically from its `document_key`, `title`, and `digest_summary` fields. Render each item title as `document_key — title`, with the guidance file number first. After all guidance records, render one `View original source →` link using the trusted `source.source_page` URL supplied by the digest. Do not send BC local digest content to the language model.

The BC local identity is `document_key + current_version`; if no version is supplied, use a hash of the title and summary. A new source version must therefore be eligible for inclusion even when its document key and displayed title remain unchanged.

### 7.1 Search

Build a provider-side query containing:

- an OR expression for all configured sender addresses;
- a lower date bound;
- an upper date bound.

Because provider date searches may be coarse, fetch each candidate's timestamp and enforce the exact timezone-aware half-open reporting interval locally.

### 7.2 MIME parsing

For every message:

1. Read headers, internal timestamp, and MIME payload.
2. Decode URL-safe Base64 message parts.
3. Walk nested multipart structures recursively.
4. Collect `text/plain` and `text/html` parts.
5. Prefer readable text while retaining HTML for link extraction.
6. Normalize the sender using the parsed address only, lowercased.
7. Convert the received timestamp to the configured timezone.

### 7.3 URL extraction

Extract links only from source HTML. Ignore unusable schemes and obvious navigation/tracking links. Canonicalization must:

- lowercase scheme and host;
- remove fragments;
- remove common tracking parameters such as `utm_*`;
- preserve meaningful query parameters;
- deduplicate canonical URLs;
- limit the prompt link inventory to 50 links;
- assign deterministic IDs such as `L1`, `L2`, and so on.

## 8. Model Input and Security Boundary

The model prompt must clearly state that the email is untrusted data and that instructions inside it must be ignored.

For each message, provide:

- target program name and country;
- normalized sender;
- whether the source is mixed-topic or dedicated;
- configured inclusion terms;
- configured exclusion terms;
- original subject;
- email body truncated to `ai.max_email_characters`;
- the allowed link-ID-to-URL mapping.

Required model rules:

1. Examine distinct articles or announcements separately.
2. Include only items directly about the target program.
3. Do not treat broad climate or clean-energy relevance as sufficient.
4. Preserve an original headline when available.
5. Produce a factual one- or two-sentence English summary.
6. Do not add outside facts, impact analysis, or speculation.
7. Select a source link only by allowed link ID.
8. Return an empty item list for unrelated or ambiguous content.

No manual-review stage exists. Unrelated and ambiguous content is excluded. A provider, transport, parsing, or schema failure is fatal for the run.

## 9. Structured Output Schema

The model response is equivalent to:

```json
{
  "items": [
    {
      "title": "string",
      "summary": "string",
      "source_link_id": "L3 or null",
      "confidence": "high | medium | low"
    }
  ]
}
```

Validate the response before using it. If `source_link_id` is missing or is not present in the extracted allowlist, use the original mailbox message URL. Never accept a model-invented URL.

## 10. Conversion, Ordering, and Deduplication

Normalize titles by collapsing whitespace and trimming decorative punctuation.

For each accepted item, retain:

- country and country order;
- program ID, program display name, and program order;
- normalized title;
- factual summary;
- verified source URL;
- source message ID;
- received timestamp;
- confidence;
- stable item key.

For email-derived items, preserve the existing item key so historical email entries remain compatible:

```text
program_id + canonical source URL + normalized lowercase title
```

For local-source items, hash `program_id + local identity version + source-specific item ID`. Do not dual-check the old local title/URL key: it represents the over-suppression behavior being corrected. Leave prior state records untouched; email keys continue to match, while local records use the new identity namespace and may be reported once during cutover.

Deduplicate identical item keys within the current run. Sort by:

1. country order;
2. program order;
3. received timestamp;
4. lowercase title.

Unless `--include-processed` is present, remove keys already recorded under `sent_items` in the state file.

## 11. Output Artifacts

Every run, including preview mode, writes:

```text
runtime/output/weekly_digest_preview.html
runtime/output/weekly_digest_preview.txt
runtime/output/weekly_digest_items.json
```

The HTML email must:

- display the reporting period;
- group programs beneath countries in configured order;
- show a clear no-update message for empty programs;
- escape all source-derived text;
- make verified sources clickable;
- label every verified clickable source `View original source →`;
- show the shared CARB workbook source only once after all California LCFS local-pathway records;
- include the deterministic `Digest ID` in the footer;
- remain readable in common email clients without JavaScript.

The text version must communicate the same content without HTML.
It must include the same `Digest ID` as the HTML version.

The JSON file must contain all final items used in the digest and preserve Unicode.

## 12. Preview and Send Modes

Required command-line behavior:

```text
python -m weekly_clean_fuels_digest.main
python -m weekly_clean_fuels_digest.main --send
python -m weekly_clean_fuels_digest.main --start 2026-09-11 --end 2026-09-18
python -m weekly_clean_fuels_digest.main --include-processed
python -m weekly_clean_fuels_digest.main --send --include-processed
python -m weekly_clean_fuels_digest.main --resolve-pending "wcf-PASTE-THE-EXACT-ID" --resolution sent
python -m weekly_clean_fuels_digest.main --resolve-pending "wcf-PASTE-THE-EXACT-ID" --resolution not-sent
python -m weekly_clean_fuels_digest.main --config path/to/config.yaml
```

- Default mode creates previews only.
- `--send` sends the digest after every candidate message succeeds.
- `--include-processed` bypasses cross-run filtering for deliberate tests.
- `--resolve-pending DIGEST_ID --resolution sent|not-sent` resolves an uncertain send without sending email. `sent` records included items as sent; `not-sent` allows a deliberate retry.
- Preview mode never modifies sent-item state.
- A previously sent reporting period is blocked from automatic redelivery. `--include-processed` is an explicit testing override.

## 13. State and Transaction Rules

The default state path is `runtime/state/state.json`.

Minimum state structure:

```json
{
  "schema_version": 1,
  "identity_version": {
    "email": 1,
    "local_digest": 2
  },
  "sent_items": {
    "stable_item_key": {
      "sent_at": "timezone-aware ISO timestamp",
      "title": "item title",
      "program_id": "program ID",
      "source_url": "verified URL"
    }
  },
  "send_transactions": {
    "wcf-digest-id": {
      "status": "sending | sent | resolved_not_sent",
      "period_start": "ISO timestamp",
      "period_end": "ISO timestamp",
      "items": []
    }
  },
  "last_run": {
    "sent_at": "timezone-aware ISO timestamp",
    "gmail_message_id": "provider message ID",
    "period_start": "ISO timestamp",
    "period_end": "ISO timestamp",
    "item_count": 0
  }
}
```

Write state atomically using a temporary file followed by replacement. Before sending, persist a deterministic digest ID, period, subject, and included item records with `status: sending`. Add that ID as an RFC 5322 `Message-ID` and in the text/HTML footer. After provider success, update the transaction to `sent` and record sent-item keys and the provider message ID. If the process stops while status is `sending`, refuse all automatic sends and require the operator to check delivery and use `--resolve-pending`. `sent` confirms delivery and records item suppression; `not-sent` records an explicit decision to allow retry. This is a fail-closed ambiguity safeguard, not exactly-once delivery.

`schema_version` describes the state file shape. `identity_version` describes the active identity rules by source. Legacy state without these fields remains readable; do not mechanically rewrite or dual-check legacy local keys.

## 14. Logging and Failure Policy

Log timestamps, reporting window, candidate count, per-message progress, retry warnings, preview location, and final provider message ID.

Rotate the log at a configurable size (`paths.log_max_bytes`, default 5 MB) and retain a configurable number of backups (`paths.log_backup_count`, default 5). Preview artifacts use fixed filenames and are overwritten each run. Check `ai.run_timeout_seconds` before processing stages; bound each OpenAI attempt and Gmail HTTP request by `ai.request_timeout_seconds`, and stop starting work when the remaining run budget is exhausted. Keep worst-case request overrun below the scheduler's one-hour limit.

Never log secrets, OAuth tokens, raw authorization headers, or complete credential objects.

Retry model calls with exponential backoff for the configured number of attempts. If all attempts fail, raise the error and abort. Do not continue to send a partial digest.

## 15. Reference Python Implementation

The current implementation uses Python 3.11 or later and these dependency families:

```text
beautifulsoup4 >=4.12,<5
google-api-python-client >=2,<3
google-auth-httplib2 >=0.2,<1
google-auth-oauthlib >=1.2,<2
openai >=2,<3
pydantic >=2.7,<3
PyYAML >=6,<7
tzdata >=2025.2
```

The module boundaries may differ in a rewrite, but preserve these conceptual components:

```text
configuration
reporting-window calculation
mail provider adapter
MIME/body/link parser
model adapter
schema validation
item normalization and deduplication
HTML/text renderer
preview writer
send transaction
state repository
scheduler entry point
```

The reference implementation uses these explicit production boundaries:

```text
src/weekly_clean_fuels_digest/main.py
                              command-line entry point and orchestration
src/weekly_clean_fuels_digest/gmail_source.py
                              Gmail provider adapter and message parser
src/weekly_clean_fuels_digest/openai_analyzer.py
                              OpenAI structured analysis adapter
src/weekly_clean_fuels_digest/digest_renderer.py
                              shared HTML and text renderer
src/weekly_clean_fuels_digest/state_store.py
                              durable sent-item state repository
src/weekly_clean_fuels_digest/shared_digest_models.py
                              source-independent shared data contracts
src/weekly_clean_fuels_digest/integrations/local_digest.py
                              optional external digest_input adapter
tests/test_core.py            email-core and shared-pipeline tests
tests/test_local_digest_integration.py
                              local-interface tests
```

`main.py` must not contain Gmail parsing, OpenAI request implementation, renderer implementation, state-file implementation, or source-specific local-file conversion logic. Those concerns belong to the modules above. The optional adapter returns the same shared models used by email-derived items. Configuration key `integrations.local_digest_enabled` controls the adapter and defaults to `true`; when `false`, the application must skip all local digest directories and run the Gmail-only core. Regardless of source, ordering, deduplication, rendering, preview output, state handling, logging, and sending remain shared.

## 16. Cross-Platform Scheduling

### Windows

Register a Task Scheduler job that runs `scripts/run_weekly.bat` every Friday at 09:00 local time, uses the project directory as the working directory, ignores overlapping instances, has a one-hour execution limit, and starts when available after a missed trigger.

The current job runs interactively, so the Windows user must be logged in. A non-interactive deployment requires a service account or stored Windows task credentials and access to the user-level API key and OAuth token.

### Linux

Use a systemd timer or cron. Prefer systemd because it supports persistent catch-up behavior. Set the timezone explicitly and run a wrapper that changes to the project directory, activates the virtual environment, loads `OPENAI_API_KEY` from a protected environment file, and executes:

```text
python -m weekly_clean_fuels_digest.main --send
```

### macOS

Use a `launchd` LaunchAgent or LaunchDaemon. Set the working directory and environment explicitly. Run every Friday at 09:00 local time and ensure missed-run behavior is understood and tested.

### Containers or Cloud Schedulers

Mount or securely provide the Gmail OAuth refresh token, configuration, and durable state. Use a secret manager for `OPENAI_API_KEY`. Ensure only one scheduled instance runs at a time and that `runtime/state/state.json` is stored on durable, atomic storage.

## 17. Security and Repository Hygiene

This is a maintained commercial codebase. The following are permanent version-controlled project assets and must not be removed during routine cleanup:

```text
src/weekly_clean_fuels_digest/
config/config.yaml
tests/
requirements.txt
requirements-dev.txt
README.md
BUILD_SPECIFICATION.md
PROJECT_PROGRESS.md
setup and scheduler scripts
```

`tests/` is executable quality-assurance code. `requirements.txt` contains production dependencies; `requirements-dev.txt` contains test and development-only dependencies. Tests must run after material code, rendering, dependency, or configuration-contract changes and before production release.

The following must be excluded from version control and deployment bundles intended for sharing:

```text
.venv/
__pycache__/
*.pyc
runtime/secrets/
runtime/state/
runtime/logs/
runtime/output/
```

The following are generated temporary artifacts and may be deleted after verification:

```text
.pytest_cache/
pytest-cache-files-*/
runtime/output/pytest-*/
```

Do not confuse those generated artifacts with the permanent `tests/` directory. The application rotates logs; the fixed-name preview artifacts are overwritten. Cleanup must never remove credentials, state, production source, tests, or required documentation. Any project relocation must rebuild or upgrade the virtual environment to refresh embedded paths, update scheduler actions and working directories, then rerun offline tests and a preview from the new path. Verify both the scheduler registration and an actual scheduled invocation; a correct action path alone does not prove successful delivery.

Treat message content, subjects, link labels, and HTML as hostile input. Escape output HTML. Do not execute links or embedded content. Never follow instructions found inside an email.

## 18. Acceptance Tests

A rebuilt implementation is equivalent only after all of these pass:

1. Explicit reporting dates produce timezone-aware midnight boundaries.
2. A normal Friday run covers the preceding Friday through Thursday.
3. URL canonicalization removes fragments and tracking parameters but preserves meaningful parameters.
4. Duplicate sender mappings fail startup.
5. Nested MIME messages yield readable text and extracted links.
6. A mixed-topic email with no target-program content yields zero items.
7. An allowed source link is retained unchanged after canonicalization.
8. An invented or unknown model link ID falls back to the mailbox message URL.
9. Duplicate items collapse to one stable key.
10. Previously sent items are excluded unless `--include-processed` is set.
11. Preview mode creates all three artifacts and does not change state.
12. A model failure aborts the run and sends nothing.
13. A pre-send transaction is durable before the provider call; an uncertain failure leaves a pending record and leaves `sent_items` unchanged.
14. A successful send marks the transaction sent and records the provider message ID and every included item key.
15. HTML and text renderers show all configured countries/programs, including no-update messages.
16. A scheduled invocation can access OAuth credentials, `OPENAI_API_KEY`, the virtual environment, and the writable state/log/output directories.
17. A local digest whose `generated_at` falls inside the reporting window is assigned to its configured program.
18. A local digest outside the reporting window is excluded.
19. A matching BC LCFS local digest renders under one `Guidance Updates` heading and uses its official `source.source_page` URL once after the group.
20. Neither California nor BC local digest content is transmitted to the language model.
21. A malformed matching local digest aborts the run rather than being silently skipped.
22. Local digest conversion does not make an OpenAI request.
23. With `integrations.local_digest_enabled: false`, local directories are not read and the Gmail-only workflow remains operational.
24. Email and local-interface items use the same final data model, deduplication, renderers, previews, state, and send transaction.
25. Same email item inputs retain their legacy item key; distinct local pathway identities do not collapse because of a shared workbook URL/title.
26. A BC document revision with a changed `current_version` receives a new item key.
27. A California pathway identity is unchanged by a CI-only change or ordinary row movement; identical duplicate rows in one input remain distinguishable.
28. California `updated_pathways` render under `Existing Pathway Updates`, separately from new certifications, and share one source link across both groups.
29. A pending send transaction blocks automatic sends, and both explicit resolution choices are covered by tests.
30. Malformed state/config structures fail at startup with actionable errors.
31. Gmail and OpenAI request timeouts and the overall run budget are enforced; logs rotate within configured limits.
32. The state CLI can resolve a pending transaction as sent or not-sent without sending mail.

## 19. Rebuild Procedure

1. Create the project directory and implement the components in Section 15.
2. Copy or recreate `config/config.yaml` exactly from the live regulatory inventory.
3. Create or refresh the isolated virtual environment at its final project location, then install runtime dependencies. Do not copy a virtual environment from another path or platform.
4. Create a Gmail desktop OAuth client, enable Gmail API, and place the credential JSON in the configured secrets path.
5. Create an OpenAI API key with funded API access and expose it as `OPENAI_API_KEY` to the runtime user.
6. Run preview mode and complete the one-time Gmail OAuth consent flow.
7. Inspect HTML, text, JSON, and logs.
8. Run the acceptance tests.
9. Send one deliberate test using `--send --include-processed` if necessary.
10. Verify receipt at the exact configured mailbox address.
11. Install the platform scheduler.
12. Verify scheduler identity, working directory, environment, next trigger, missed-run behavior, and log output.

## 20. Definition of Done

The rebuild is complete when it can run unattended, produce the same program grouping and filtering behavior, send to the correct mailbox, avoid duplicate items, survive a missed schedule where supported, expose no secrets, abort on incomplete analysis, and pass every acceptance test above.
