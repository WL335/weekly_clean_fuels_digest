# Weekly Clean Fuels Regulatory Digest — Project Progress

## Status Summary

**Overall status:** Operational

**Status date:** September 29, 2026 (`America/Regina`)

The end-to-end workflow has been implemented and exercised successfully: Gmail OAuth, regulatory-message discovery, GPT-5 nano analysis, structured-output validation, digest generation, email delivery, persistent deduplication, and Windows Task Scheduler registration.

## Completed

- [x] Created the Python application and YAML-driven regulatory inventory.
- [x] Added Gmail OAuth with read-only and send scopes.
- [x] Authorized the mailbox `wenli.insight@gmail.com`.
- [x] Corrected the original recipient typo from `wenli.inslight@gmail.com` to `wenli.insight@gmail.com`.
- [x] Installed the isolated Python virtual environment and dependencies.
- [x] Added Windows timezone data required for `America/Regina`.
- [x] Migrated the summarization provider from Gemini to the OpenAI API.
- [x] Configured `gpt-5-nano` for classification, extraction, and summarization.
- [x] Added Pydantic-backed structured output validation.
- [x] Confirmed that source URLs must come from the source email.
- [x] Added original Gmail-message URL fallback for missing or invalid link IDs.
- [x] Added same-run and cross-run deduplication.
- [x] Added HTML, text, and JSON preview artifacts.
- [x] Removed the manual-review workflow by request.
- [x] Configured unrelated or ambiguous messages to return zero items.
- [x] Configured analysis failures to abort the entire run instead of sending an incomplete digest.
- [x] Removed all active `GEMINI_API_KEY` checks and documentation references.
- [x] Confirmed active runtime checks use only `OPENAI_API_KEY`.
- [x] Successfully sent test digests through Gmail.
- [x] Registered the Windows scheduled task `Weekly Clean Fuels Regulatory Digest`.
- [x] Configured the task for Fridays at 09:00 local time with `StartWhenAvailable`.
- [x] Added a platform-independent rebuild specification.
- [x] Added a second California LCFS source from the local `digest_input` JSON directory.
- [x] Matched local digests to weekly periods using `generated_at`, with file modification time as fallback.
- [x] Merged local digest items into the existing California LCFS grouping, validation, ordering, and deduplication flow.
- [x] Kept local digest contents private by converting structured pathways locally without an OpenAI request.
- [x] Added the requested `Newly Certified Pathway(s)` presentation and one shared CARB workbook source link.
- [x] Standardized every verified HTML source link label as `View original source →`; ordinary email items display it per item, while the California LCFS local-pathway subsection displays it once after all pathways.
- [x] Moved the production project to `D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest`.
- [x] Updated the Windows scheduled task action and working directory to the new production path.
- [x] Removed generated pytest caches and temporary test work directories while retaining the permanent `tests/` suite and `requirements-dev.txt`.
- [x] Verified the relocated application starts correctly and passed the targeted offline regression tests.
- [x] Adopted a commercial project-maintenance policy covering test retention, dependency separation, secret handling, temporary-artifact cleanup, documentation synchronization, and output/log retention.
- [x] Added the BC LCFS `digest_input` directory as a second deterministic local-program feed.
- [x] Added BC guidance conversion from `title` and `digest_summary` without sending local content to OpenAI.
- [x] Prefixed each BC guidance title with its `document_key` file number (for example, `RLCF-009 — ...`).
- [x] Added the `Guidance Updates` subsection under BC Low Carbon Fuel Standard (LCFS), with one official source link after the complete group.
- [x] Added BC local-digest regression coverage.
- [x] Adopted a standard `src/weekly_clean_fuels_digest` Python package layout.
- [x] Split Gmail access, OpenAI analysis, rendering, state storage, shared models, and local integrations into explicitly named modules.
- [x] Kept `main.py` focused on command-line entry and common orchestration.
- [x] Moved configuration to `config/config.yaml`, operating scripts to `scripts/`, and all mutable operating data to `runtime/`.
- [x] Added `cleanfuel.standard@env.nm.gov` as a second New Mexico CTFP Gmail source while retaining the existing NMED source.
- [x] Added the default-on `integrations.local_digest_enabled` toggle; setting it to `false` selects the Gmail-only workflow.
- [x] Split core tests from local-interface tests; the full offline suite now passes 8 tests.
- [x] Preserved the legacy email item-key recipe while moving local digest records to source-specific identity version 2.
- [x] Identified California pathways by upstream pathway ID when available, otherwise by stable company/fuel/class/description fields; CI and ordinary row position do not change pathway identity.
- [x] Retained `source_row` only as a tie-breaker for otherwise identical records within one input file, favoring visible duplicates over silent merging.
- [x] Added BC local identity based on `document_key` and `current_version`, with a title/summary content-hash fallback.
- [x] Added support for optional California `updated_pathways` records under a separate `Existing Pathway Updates` subsection; the current feed sample has no such records yet.
- [x] Kept one CARB workbook source link after both California pathway groups.
- [x] Added state `schema_version` and per-source `identity_version`; legacy state remains readable and is not mechanically rewritten or dual-checked.
- [x] Added deterministic digest IDs, Message-ID/footer markers, pre-send transaction recording, fail-closed pending-send handling, and `--resolve-pending` recovery choices.
- [x] Added startup structure validation, parameterized default seven-day reporting-window tests, bounded Gmail/OpenAI request timeouts, and an overall 55-minute work budget.
- [x] Added configurable log rotation (5 MB, five backups by default); preview artifacts continue to overwrite fixed filenames.
- [x] Expanded the offline suite with identity regressions, provider-schema compatibility, state compatibility, pending-send resolution, Message-ID markers, and update rendering coverage.
- [x] Added failure notification through channels independent of the mail transport: a `runtime/state/last_failure.json` record, a Windows `msg.exe` popup, a date-stamped Desktop marker file, and a best-effort Windows Application event log entry. Every channel records whether it succeeded.
- [x] Split process exit codes so a configuration or credential failure (`2`) is distinguishable from a runtime failure (`1`) in Task Scheduler history.
- [x] Moved the `OPENAI_API_KEY` presence check into the application so a missing key is reported through the alert channels instead of only as a batch-file exit code.
- [x] Added an independent delivery watchdog (`weekly_clean_fuels_digest.watchdog`, `scripts\run_watchdog.bat`) with its own Saturday Task Scheduler entry. It uses no mail transport, needs no OpenAI key, judges a period by that period's own send transaction, allows a configurable grace period after the scheduled send time, reports an unresolved pending transaction separately, and notifies at most once per missed period.
- [x] Added the `alerts.*` configuration section with startup validation for the notification switches and the grace period.
- [x] Moved digest-ID insertion out of a string replacement in `main.py` into a `digest_id` argument on both renderers, removing the cross-module markup coupling.
- [x] Moved `send_digest` into the Gmail provider adapter, where the rebuild specification places mail sending, and dropped the now-unused `base64` and `EmailMessage` imports from `main.py`.
- [x] Applied the public-URL check to the plain-text renderer as well, so a local digest without a public source URL no longer leaks a `file:///` path into the plain-text email.
- [x] Added a GitHub Actions workflow that runs the offline suite on Windows for Python 3.11 and 3.13 with no Gmail access, no delivery, no production key, and a guard against tracked credentials.
- [x] Collapsed the duplicated subsection rendering into one section table (`SECTION_SPECS`) plus one grouping step (`layout_program`) shared by both formats. Adding a subsection is now one table entry instead of edits in four near-identical render blocks.
- [x] Encoded the link-scope rules in that table: the two California pathway groups share one workbook link, guidance has its own, and ordinary items carry a link each.
- [x] Added renderer snapshot tests against a frozen fixture configuration, so the live regulatory inventory no longer churns the expected output. HTML and plain text stayed byte-identical through the refactor.
- [x] Broadened the run failure handler to every exception, so provider credential errors such as `google.auth.exceptions.RefreshError` are reported through the alert channels instead of escaping as a bare traceback.
- [x] Made the watchdog alert when it cannot read its own configuration or state, retry an alert that reached no notification channel, and report a failed `--test-alert` as a failure instead of success.
- [x] Made the watchdog require a record that covers the whole reporting week, and added `alerts.watchdog_armed_from` so a lost state file or a never-successful first automatic send can no longer suppress alerts indefinitely.
- [x] Required period timestamps in state to be timezone-aware at validation, and made the watchdog treat an unprovable record as unaccounted for rather than letting a naive-versus-aware comparison escape the check.
- [x] Added a last-resort guard around the whole watchdog flow, so any unexpected failure still notifies through the alert channels.
- [x] Required display proof before a timed-out message box counts as a delivered notification.
- [x] Removed that shared display-proof file again: a timeout is now always unconfirmed, so a stale or concurrently written marker can no longer make an undelivered alert look delivered, and the retry stays in place unless another channel delivers.

## Current Runtime Configuration

| Setting | Current value |
|---|---|
| Production project path | `D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest` |
| Mail account | `wenli.insight@gmail.com` |
| Sender | `wenli.insight@gmail.com` |
| Recipient | `wenli.insight@gmail.com` |
| Model provider | OpenAI API |
| Model | `gpt-5-nano` |
| Summary language | English |
| Timezone | `America/Regina` |
| Schedule | Every Friday at 09:00 local time |
| Reporting period | Previous Friday 00:00 to current Friday 00:00 |
| Normal mode | Preview only |
| Scheduled mode | Send |
| Manual review | Disabled |
| Failure policy | Abort; do not send partial digest |
| Local digest integration | Enabled by default (`integrations.local_digest_enabled: true`) |
| OpenAI request timeout | 90 seconds per attempt |
| Overall run budget | 55 minutes |
| Log rotation | 5 MB per file; five backups |
| Failure alerts | `msg.exe` popup, Desktop marker file, Windows event log (all enabled) |
| Watchdog schedule | Every Saturday at 09:00 local time |
| Watchdog grace period | 6 hours after the scheduled Friday 09:00 send (`alerts.grace_hours`) |
| Process exit codes | `0` success; `1` failure during the run, including credential errors; `2` startup or configuration failure, including a missing API key; `3` watchdog alert; `4` watchdog alert undelivered |
| California LCFS local source | `D:\WorkSpace\Code\RegProgram_Automation\program\CA_LCFS\digest_input` |
| BC LCFS local source | `D:\WorkSpace\Code\RegProgram_Automation\program\BC_LCFS\digest_input` |
| Source-link label | `View original source →` |

## Latest Recorded State

The following values were read from the live local state on September 26, 2026:

| Field | Value |
|---|---|
| Latest successful send timestamp | `2026-09-25 09:35:13` local time |
| Latest Gmail message ID | `1a0d934d20190003` |
| Latest recorded period start | `2026-09-18 00:00:00` |
| Latest recorded period end | `2026-09-25 00:00:00` |
| Items in latest send | `1` |
| Total item keys in deduplication state | `32` |
| Items in current preview JSON | `1` (latest completed reporting period) |

These are mutable operational values, not design constants. Future successful sends will update them.

## Scheduler Status

The Windows scheduled task was installed successfully with these settings:

```text
Task name: Weekly Clean Fuels Regulatory Digest
Executable: C:\Windows\System32\cmd.exe
Command: /c "<project>\scripts\run_weekly.bat"
Working directory: D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest
Trigger: Friday at 09:00 local time
Start when available: enabled
Multiple instances: ignore new instance
Execution limit: 1 hour
Logon type: Interactive
```

The live registered task action and working directory were read-only checked on September 29, 2026; both point to the `D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest` deployment. Task Scheduler reports its latest run was September 27 at 5:33 PM with result code 0, and the next run is Friday, October 2 at 9:00 AM. The Sunday run is not evidence of a Friday scheduled delivery; confirm the next scheduled run and receipt separately.

Operational consequence: the computer must be powered on and the Windows user must be logged in. If the scheduled time is missed while the task cannot run, Task Scheduler is configured to start it when available.

## Verified Behaviors

- Gmail candidate messages can be listed for an explicit weekly period.
- OAuth refresh credentials persist between runs.
- GPT-5 nano requests return successful Responses API results.
- All processed model responses conform to the application schema.
- A preview can be generated without sending or modifying state.
- A successful Gmail send returns and records a Gmail message ID.
- The corrected mailbox address receives the digest.
- Previously sent item keys are filtered from later normal runs.
- `--include-processed` permits an explicit testing override; transaction records still prevent repeating the same override digest.
- No `review_required.json` file is generated.
- The relocated application starts from the new production directory.
- Targeted offline regression tests pass after relocation.
- No generated pytest cache or test work directory remains in the production tree after cleanup.
- BC LCFS local guidance is included only when `generated_at` falls within the reporting period, appears under `Guidance Updates`, and links once to the official BC source page.
- Legacy email item keys remain compatible; local source identity regressions are covered by tests.
- A pending send is persisted before the provider call and can be resolved through the CLI rather than manual state-file editing.
- The Task Scheduler action and working directory both point to the production Code path. A delivered send is recorded for the period ending 2026-10-02 (sent 09:12 local time, Gmail message ID `1a0fd2ce718f103a`, 16 items).
- Disabling `integrations.local_digest_enabled` bypasses the optional local interface while preserving the Gmail core and shared output pipeline.
- A failed send-mode run writes `runtime/state/last_failure.json`, shows a message box, and writes a Desktop marker file; every channel reports its own outcome in the log.
- Alert channels were exercised for real on the production machine on 2026-10-04: the Desktop marker was written (`C:\Users\48596\Desktop\Weekly Digest ALERT 2026-10-04.txt`) and the message box was displayed and acknowledged by the operator. `msg.exe` is not installed on this machine, so the PowerShell message box fallback is the path that ran. `eventcreate.exe` returned `Access is denied`, so the event-log channel is disabled in configuration.
- The watchdog was run against live state: it reported `ok` for the period ending 2026-10-02 and wrote no alert bookkeeping, confirming it does not raise a false alarm for a delivered period.
- Rendered HTML and plain text match the recorded snapshots byte for byte after the section-table refactor, and the link-scope rule is asserted inside the California cluster rather than across the whole document.
- A Gmail credential failure (`RefreshError`) aborts the run with exit code 1 and writes a failure record naming the stage, rather than escaping with no notification.
- The watchdog notifies when it cannot read its own configuration or state; when no channel delivers an alert it leaves the period unmarked so the next check retries; and a `--test-alert` that reaches nobody returns exit code 4 instead of success.
- A one-day report does not satisfy the weekly delivery check while a longer catch-up report does, and with `alerts.watchdog_armed_from` set a watchdog with no send history at all still alerts.
- A timezone-naive timestamp in state is rejected at load with an actionable error, and a naive send record cannot prove delivery without silencing the watchdog.
- A message box that is not acknowledged within its timeout is reported as unconfirmed, and an earlier successful popup cannot make a later timeout count.
- The offline suite passes 75 tests (run `pytest -q` for the current count).

## Known Constraints

1. The scheduled task currently uses an interactive Windows logon token.
2. The computer must have network access at execution time.
3. Gmail OAuth test-mode access depends on the authorized Google account remaining an allowed test user until the app is published or otherwise reconfigured.
4. OpenAI API calls require positive API credit and access to `gpt-5-nano`.
5. Provider pricing, model availability, and API schemas can change; dependency upgrades must be tested before deployment.
6. Regulatory sender addresses and terminology can change and must be maintained in `config/config.yaml`.
7. The current tests are lightweight and do not yet constitute a full mocked integration suite.
8. Historical logs contain earlier Gemini migration errors. They are inert history and do not affect the current OpenAI implementation.
9. The old project location may retain an empty directory until the previous workspace process releases its Windows filesystem handle; it contains no application files and does not affect production.
10. The virtual environment metadata and text activation scripts now point to the new project path. Some generated console-launcher `.exe` files still contain the old absolute path; the scheduled wrapper and verified tests invoke `.venv\Scripts\python.exe` directly, so use `python -m ...` commands or rebuild the environment before relying on those launcher executables.
11. The current California input schema contains `added_pathways` only; `Existing Pathway Updates` will remain empty until the upstream producer supplies `updated_pathways` records with prior/current CI values.
12. The delivery watchdog runs on the same computer as the digest. It cannot report a period in which the machine was powered off, or nobody was logged in, for the whole time; covering that case would require an off-machine heartbeat.
13. Alert delivery depends on the session: the Windows event-log channel needs an elevated task and is therefore disabled, the message box needs an interactive session, and the Desktop marker is the only channel that works with nobody logged in.

## Commercial Repository Standard

- `tests/` and `requirements-dev.txt` are permanent project assets and must remain with the codebase.
- Generated test caches and work directories are disposable and must be excluded from source control.
- Runtime credentials remain only in `runtime/secrets/` and must never be committed, logged, or included in shared bundles.
- Production and development dependencies remain separated in `requirements.txt` and `requirements-dev.txt`.
- Material changes require regression testing, preview inspection, and synchronized updates to all three project documents; continuous integration enforces the offline suite on every push.
- Logs rotate at a configured size; fixed-name previews are overwritten. State is intentionally retained without pruning.

## Recommended Next Improvements

- [ ] Add mocked Gmail API integration tests covering ambiguous delivery failure and end-to-end transaction recovery.
- [ ] Add a dry-run summary showing candidate, included, excluded, and duplicate counts.
- [x] Add startup validation for core YAML sections and required program/source fields.
- [x] Add configurable log rotation; preview files are overwritten and state is retained.
- [ ] Add a health-check command that verifies credentials, paths, model access, and scheduler visibility without sending mail.
- [ ] Consider a non-interactive service identity if the digest must run while the Windows user is logged out.
- [x] Added local failure notification (popup, Desktop marker, Windows event log) and an independent Saturday delivery watchdog without adding an external service or dependency.
- [x] Verified the alert channels on the production machine with `scripts\run_watchdog.bat --test-alert`: the message box was displayed and acknowledged, and the Desktop marker was written. The event-log channel was disabled because it requires elevation.
- [ ] Consider an off-machine heartbeat if whole-week downtime must also be detected.
- [ ] Review the regulatory program inventory quarterly.

## Operating Checklist

### Before each scheduled period

- No manual action is normally required.
- Ensure the computer will be on and the user logged in Friday morning.
- Ensure the OpenAI API account has available credit.

### After a scheduled run

- Confirm receipt of the digest.
- If missing, inspect `runtime/logs/weekly_digest.log` and Windows Task Scheduler history.
- Do not delete `runtime/state/state.json` unless deliberate resending is intended.

### When changing programs or senders

1. Edit `config/config.yaml` only.
2. Run preview mode.
3. Inspect the generated HTML, text, and JSON.
4. Confirm sender uniqueness.
5. Send a deliberate test if the change is material.

### When changing model providers

1. Preserve the structured-output schema and prompt safety boundary.
2. Preserve the allowed-link enforcement.
3. Preserve the fatal failure policy.
4. Run every acceptance test in `BUILD_SPECIFICATION.md`.
5. Update requirements, environment-variable documentation, setup scripts, and scheduler wrappers together.

## Reference Documents

- `BUILD_SPECIFICATION.md` — complete platform-independent rebuild contract.
- `README.md` — operator setup and usage instructions for the current Windows/Python implementation.
- `config/config.yaml` — authoritative live mailbox, schedule, model, and regulatory-program configuration.
- `requirements.txt` — current Python dependency contract.
