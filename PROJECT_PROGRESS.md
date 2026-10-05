# Weekly Clean Fuels Regulatory Digest — Project Progress

## Status Summary

**Overall status:** Implemented and merged; successful sending recorded; next scheduled end-to-end verification outstanding

**Status date:** October 4, 2026 (`America/Regina`)

The end-to-end workflow has been implemented and exercised: Gmail OAuth, regulatory-message discovery, GPT-5 nano analysis, structured-output validation, digest generation, email sending, persistent deduplication, and Windows Task Scheduler registration. Both digest and watchdog tasks point to the production Code path. A successful send is recorded, but the latest digest task result is non-zero and the watchdog has no confirmed scheduled run; registration and manual verification must not be presented as proof of unattended success.

**Merged reference:** `main` at `dd82c63` (`Merge pull request #1 from WL335/DS-fix`), containing the reviewed changes through `c47dab8`. Local `main` matches the locally recorded `origin/main`; no live GitHub CI result was queried during this documentation update.

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
- [x] Split core tests from local-interface tests and expanded the full offline suite to 75 passing tests as of this status date.
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
- [x] Added independent failure notification: a `runtime/state/last_failure.json` record, a popup through `msg.exe` or a PowerShell fallback, a date-stamped Desktop marker, and an optional Windows Application event-log channel. Production enables popup and Desktop marker; event log is disabled after its permission failure. Every attempted channel records its outcome.
- [x] Split application exit codes into startup/configuration failure (`2`, including a missing key or unusable state) and runtime failure (`1`, including provider and credential errors). Batch runners return `1` without application alerts if the Python executable is missing.
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
- [x] Finalized popup semantics in `c47dab8`: every timeout is unconfirmed; the earlier shared display-proof approach was removed so stale or concurrent markers cannot make an undelivered alert count. Retry remains eligible unless another notification channel succeeds.
- [x] Merged PR #1 into `main` at `dd82c63` and reconciled all three English project documents with that code, live configuration, and dated operational evidence.

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
| Failure alerts | Popup and Desktop marker enabled; Windows event log disabled |
| Popup on this machine | PowerShell message box fallback; `msg.exe` is absent |
| Watchdog schedule | Every Saturday at 09:00 local time |
| Watchdog grace period | 6 hours after the scheduled Friday 09:00 send (`alerts.grace_hours`) |
| Watchdog arming | `alerts.watchdog_armed_from: "2026-10-09"` (first period end that must alert even with no send history) |
| Digest application exit codes | `0` success; `1` runtime failure, including provider/credential errors; `2` startup/configuration/state failure, including a missing key |
| Watchdog exit codes | `0` no alert required or test channel success; `2` configuration/state/check failure; `3` missing/pending period, including one already reported; `4` required/test notification undelivered |
| Batch wrapper failure | Missing virtual-environment Python returns `1` before application alerting can run |
| CI triggers | Pushes to `main`/`DS-fix` and pull-request events; Windows, Python 3.11 and 3.13 |
| California LCFS local source | `D:\WorkSpace\Code\RegProgram_Automation\program\CA_LCFS\digest_input` |
| BC LCFS local source | `D:\WorkSpace\Code\RegProgram_Automation\program\BC_LCFS\digest_input` |
| Source-link label | `View original source →` |

## Latest Recorded State

The following values were read from live local state and output on October 4, 2026. All timestamps below use `America/Regina` (UTC−06:00):

| Field | Value |
|---|---|
| Latest provider-accepted send recorded at | `2026-10-02T09:12:53.981468-06:00` |
| Latest Gmail message ID | `1a0fd2ce718f103a` |
| Latest digest ID | `wcf-ec648e5ccf15d37f47795216` |
| Latest recorded period start | `2026-09-25T00:00:00-06:00` |
| Latest recorded period end | `2026-10-02T00:00:00-06:00` |
| Items in latest send | `16` |
| Total item keys in deduplication state | `49` |
| Send transactions | `1` |
| State schema / identity versions | Schema `1`; email `1`; local digest `2` |
| Items in current preview JSON | `16` |

These are mutable operational snapshots, not design constants or continuously refreshed documentation. State records provider acceptance; it does not independently prove recipient delivery or identify which Task Scheduler invocation produced the send. Future runs can overwrite previews and update state.

## Scheduler Status

Both Windows tasks were read-only checked on October 4, 2026. Their executable is `C:\Windows\System32\cmd.exe`; actions and working directories point to the production Code deployment:

```text
Task name: Weekly Clean Fuels Regulatory Digest
Command: /c "<project>\scripts\run_weekly.bat"
Working directory: D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest
Trigger: Friday at 09:00 local time
Execution limit: 1 hour

Task name: Weekly Clean Fuels Digest Watchdog
Command: /c "<project>\scripts\run_watchdog.bat"
Working directory: D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest
Trigger: Saturday at 09:00 local time
Execution limit: 15 minutes

Both tasks:
Start when available: enabled
Multiple instances: ignore new instance
Logon type: Interactive
```

| Task | Current state | Last run/result observed | Next run (`America/Regina`) |
|---|---|---|---|
| Digest | Ready | `2026-10-02 09:00:01`; result `1` | Friday, `2026-10-09 09:00:00` |
| Watchdog | Ready | No confirmed scheduled run; raw result `267011` and placeholder last-run date | Saturday, `2026-10-10 09:00:00` |

The digest's non-zero task result is not evidence of a clean scheduled completion, even though state records a subsequent successful send at 09:12. Correlating that send with the earlier invocation would require its log/history; this documentation update did not diagnose or repair the task. The previously recorded manual watchdog check is not proof that its registered Saturday task ran. Confirm both upcoming scheduled invocations and receipt separately.

The six-hour grace period makes a missing Friday send eligible at 15:00 Friday; the installed watchdog checks Saturday at 09:00. It does not automatically notify Friday afternoon. The installer fixes Friday/Saturday 09:00 Windows-local triggers and does not read them from YAML; keep the machine timezone aligned and re-register both tasks after deployment-path or trigger changes.

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
- Generated caches and test work directories are excluded from Git; their presence is mutable and must not be confused with permanent tests.
- BC LCFS local guidance is included only when `generated_at` falls within the reporting period, appears under `Guidance Updates`, and links once to the official BC source page.
- Legacy email item keys remain compatible; local source identity regressions are covered by tests.
- A pending send is persisted before the provider call and can be resolved through the CLI rather than manual state-file editing.
- Both Task Scheduler actions and working directories point to the production Code path. State records a provider-accepted send for the period ending 2026-10-02 (09:12 local time, Gmail message ID `1a0fd2ce718f103a`, 16 items); scheduled-run success remains a separate check.
- Disabling `integrations.local_digest_enabled` bypasses the optional local interface while preserving the Gmail core and shared output pipeline.
- A handled send-mode failure attempts `runtime/state/last_failure.json` and every enabled notification channel; outcomes are recorded rather than assuming every channel succeeds. Preview failures record evidence without operator notification.
- Alert channels were exercised for real on the production machine on 2026-10-04: the Desktop marker was written (`C:\Users\48596\Desktop\Weekly Digest ALERT 2026-10-04.txt`) and the message box was displayed and acknowledged by the operator. `msg.exe` is not installed on this machine, so the PowerShell message box fallback is the path that ran. `eventcreate.exe` returned `Access is denied`, so the event-log channel is disabled in configuration.
- During the earlier implementation verification, a manual watchdog check against live state reported `ok` for the period ending 2026-10-02 and wrote no alert bookkeeping. This was not repeated during the documentation-only update and is distinct from a scheduled invocation.
- Rendered HTML and plain text match the recorded snapshots byte for byte after the section-table refactor, and the link-scope rule is asserted inside the California cluster rather than across the whole document.
- A Gmail credential failure (`RefreshError`) aborts the run with exit code 1 and writes a failure record naming the stage, rather than escaping with no notification.
- The watchdog notifies when it cannot read its own configuration or state; when no channel delivers an alert it leaves the period unmarked so the next check retries; and a `--test-alert` that reaches nobody returns exit code 4 instead of success.
- A one-day report does not satisfy the weekly delivery check while a longer catch-up report does, and with `alerts.watchdog_armed_from` set a watchdog with no send history at all still alerts.
- A timezone-naive timestamp in state is rejected at load with an actionable error, and a naive send record cannot prove delivery without silencing the watchdog.
- A message box that is not acknowledged within its timeout is reported as unconfirmed, and an earlier successful popup cannot make a later timeout count.
- On October 4, the merged code's offline suite passed 75 tests in an isolated temporary copy of `src`, `config`, and `tests`, using the production virtual-environment Python with an empty API key, bytecode/cache writing disabled, and temporary test data outside production. An initial sandboxed attempt failed on temporary-directory permissions, not assertions; the permitted isolated rerun passed (`75 passed in 1.42s`). Both CLI `--help` entry points also succeeded. No live mail, credentials, state, scheduler settings, or real alerts were exercised or changed by this check.

## Known Constraints

1. The scheduled task currently uses an interactive Windows logon token.
2. The computer must have network access at execution time.
3. Gmail OAuth test-mode access depends on the authorized Google account remaining an allowed test user until the app is published or otherwise reconfigured.
4. OpenAI API calls require positive API credit and access to `gpt-5-nano`.
5. Provider pricing, model availability, and API schemas can change; dependency upgrades must be tested before deployment.
6. Regulatory sender addresses and terminology can change and must be maintained in `config/config.yaml`.
7. The 75 offline cases cover providers, state, identity, rendering, alerts, and watchdog behavior, but do not constitute a complete end-to-end mocked Gmail delivery/recovery suite or prove live scheduler success.
8. Historical logs contain earlier Gemini migration errors. They are inert history and do not affect the current OpenAI implementation.
9. The old project location may retain an empty directory until the previous workspace process releases its Windows filesystem handle; it contains no application files and does not affect production.
10. Prior relocation checks found stale paths in some generated virtual-environment launchers. The scheduled wrappers and verified tests invoke `.venv\Scripts\python.exe` directly. Recreate the environment at its final path and reinstall dependencies before relying on generated launchers; this documentation update did not rebuild it. Direct module calls also need `PYTHONPATH=<project>/src`, because setup does not install the application package.
11. The current California input schema contains `added_pathways` only; `Existing Pathway Updates` will remain empty until the upstream producer supplies `updated_pathways` records with prior/current CI values.
12. The delivery watchdog runs on the same computer as the digest. It cannot report a period in which the machine was powered off, or nobody was logged in, for the whole time; covering that case would require an off-machine heartbeat.
13. Alert channels depend on permissions and session availability: production event log is disabled, popup needs an interactive session, and a Desktop marker can persist without a visible session only if some process runs with access to that Desktop. The current interactive tasks do not run while the user is logged out. Successful marker creation does not prove that an operator read it.
14. Cloud CI results were not fetched during this local documentation update. The workflow definition and local offline suite are verified separately from GitHub job status.

## Commercial Repository Standard

- `tests/` and `requirements-dev.txt` are permanent project assets and must remain with the codebase.
- Generated test caches and work directories are disposable and must be excluded from source control.
- Runtime credentials remain only in `runtime/secrets/` and must never be committed, logged, or included in shared bundles.
- Production and development dependencies remain separated in `requirements.txt` and `requirements-dev.txt`.
- Material changes require regression testing, preview inspection, and synchronized updates to all three project documents. CI runs on pushes to `main`/`DS-fix` and pull-request events; other branch pushes alone do not trigger the current workflow. The credential guard checks tracked `runtime/secrets/` files, not all possible secret locations.
- Logs rotate at a configured size; fixed-name previews are overwritten. State is intentionally retained without pruning.

## Recommended Next Improvements

- [ ] Verify the October 9 digest task and October 10 watchdog task actually run from the current path; correlate exit results, logs, period state, and mailbox receipt.
- [ ] Investigate the latest digest Task Scheduler result `1` separately from the successful send record; do not assume the merge or documentation update resolved it.
- [ ] Add mocked Gmail API integration tests covering ambiguous delivery failure and end-to-end transaction recovery.
- [ ] Add a dry-run summary showing candidate, included, excluded, and duplicate counts.
- [x] Add startup validation for core YAML sections and required program/source fields.
- [x] Add configurable log rotation; preview files are overwritten and state is retained.
- [ ] Add a health-check command that verifies credentials, paths, model access, and scheduler visibility without sending mail.
- [ ] Consider a non-interactive service identity if the digest must run while the Windows user is logged out.
- [x] Added popup/Desktop/optional event-log notification and an independent Saturday watchdog; production event log remains disabled.
- [x] Verified the alert channels on the production machine with `scripts\run_watchdog.bat --test-alert`: the message box was displayed and acknowledged, and the Desktop marker was written. The event-log channel was disabled because it requires elevation.
- [ ] Consider an off-machine heartbeat if whole-week downtime must also be detected.
- [ ] Review the regulatory program inventory quarterly.

## Operating Checklist

### Before each scheduled period

- No manual action is normally required.
- Ensure the computer will be on and the user logged in for both Friday's digest and Saturday's watchdog.
- Ensure the OpenAI API account has available credit.

### After a scheduled run

- Confirm receipt of the digest.
- Check both tasks' last result and next trigger, not just their registered paths.
- If missing or a task result is non-zero, inspect `runtime/logs/weekly_digest.log`, `runtime/state/last_failure.json`, Desktop alert markers, and Task Scheduler history. Compare with the period-specific transaction.
- For a `sending` transaction, verify the displayed Digest ID in the mailbox and use `--resolve-pending ... --resolution sent|not-sent`; set `PYTHONPATH` first for a direct module call. Do not hand-edit state.
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
