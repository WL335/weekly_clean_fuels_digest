# Weekly Clean Fuels Regulatory Digest

This project reads regulatory-subscription emails from `wenli.insight@gmail.com`, identifies only the configured clean-fuels program updates, generates concise summaries with the OpenAI API, and sends a grouped HTML digest back to the same Gmail account.

Documentation reconciled on October 4, 2026 against merged `main` at `dd82c63` (PR #1). Deployment snapshots and outstanding verification are recorded in `PROJECT_PROGRESS.md`; `config/config.yaml` remains the authority for live settings.

## Project documentation

- `BUILD_SPECIFICATION.md` — platform-independent requirements sufficient to rebuild an equivalent system from scratch.
- `PROJECT_PROGRESS.md` — current implementation, deployment, verification, limitations, and next-step status.

## Production project location and repository policy

The deployed Windows project is located at:

```text
D:\WorkSpace\Code\Weekly Clean Fuels Digest\weekly_clean_fuels_digest
```

Treat this repository as a maintained commercial software project. Keep `tests/` and `requirements-dev.txt` under version control: they are permanent quality-assurance assets, not temporary runtime output. Runtime dependencies belong in `requirements.txt`; development and test-only dependencies belong in `requirements-dev.txt`.

Generated caches and test work directories—such as `__pycache__/`, `.pytest_cache/`, `pytest-cache-files-*`, and `runtime/output/pytest-*`—must not be committed and may be safely removed after a test run. Do not remove `tests/` as part of cleanup. Keep credentials and tokens in `runtime/secrets/`, never in source code or version control. Logs rotate by size; fixed-name preview files are overwritten each run. Sent-item state is intentionally not pruned, so agree a retention policy before state grows materially in a long-running commercial deployment.

### Code structure

- `src/weekly_clean_fuels_digest/main.py` — command-line entry point and common orchestration.
- `src/weekly_clean_fuels_digest/gmail_source.py` — Gmail authentication, discovery, MIME parsing, links, and multipart digest delivery.
- `src/weekly_clean_fuels_digest/openai_analyzer.py` — OpenAI classification and structured summaries.
- `src/weekly_clean_fuels_digest/digest_renderer.py` — shared HTML and plain-text rendering.
- `src/weekly_clean_fuels_digest/state_store.py` — validated, atomically written sent-item and send-transaction state.
- `src/weekly_clean_fuels_digest/shared_digest_models.py` — shared validated data models used by every source.
- `src/weekly_clean_fuels_digest/integrations/local_digest.py` — optional California and BC `digest_input` interface.
- `src/weekly_clean_fuels_digest/alerts.py` — independent failure records, popup/Desktop/event-log channels, and channel outcomes.
- `src/weekly_clean_fuels_digest/watchdog.py` — independently scheduled reporting-period delivery check and alert bookkeeping.
- `tests/test_core.py` — email-core and shared-pipeline regression tests.
- `tests/test_local_digest_integration.py` — external local-interface regression tests.
- `tests/test_state_store.py` — state validation and send-transaction regressions.
- `tests/test_gmail_source.py` — Gmail-provider boundary and delivery tests.
- `tests/test_alerts.py` — notification-channel and popup-timeout tests.
- `tests/test_watchdog.py` — delivery-window, fail-closed, and alert-retry tests.
- `tests/test_rendering.py` and `tests/fixtures/` — shared-renderer snapshots and link-scope regressions.
- `scripts/` — environment setup, preview/send/watchdog runners, and two-task scheduler installation.
- `.github/workflows/ci.yml` — offline Windows test matrix and tracked-credential guard.

All sources produce the same shared `DigestItem` model. They therefore use one common ordering, deduplication, HTML/text/JSON output, state, logging, and email-delivery pipeline.

## Current scope

The digest is grouped as follows:

- United States
  - California Low Carbon Fuel Standard (LCFS)
  - Oregon Clean Fuels Program (CFP)
  - Washington Clean Fuel Standard (CFS)
  - New Mexico Clean Transportation Fuel Program (CTFP)
- Canada
  - Canada Clean Fuel Regulations (CFR)
  - BC Low Carbon Fuel Standard (LCFS)
- United Kingdom
  - UK SAF Mandate

California LCFS also has a configured local JSON digest source at:

```text
D:\WorkSpace\Code\RegProgram_Automation\program\CA_LCFS\digest_input
```

A local digest is included when its JSON `generated_at` timestamp falls within the same Friday-to-Friday reporting window. If `generated_at` is absent, the file modification time is used. `added_pathways` records appear under `Newly Certified Pathway(s)`; if the upstream digest supplies `updated_pathways`, CI changes appear separately under `Existing Pathway Updates`. An update record uses `Previous Certified CI` and `Current Certified CI`, plus the pathway fields and top-level `current_version`. Both groups share one CARB workbook link after the groups. The current upstream sample contains only `added_pathways`, so the update section appears when that feed begins supplying update records. Local content is converted without sending the file to OpenAI.

Email item identities retain the original `program + canonical source URL + normalized title` rule so existing email state remains compatible. Local records use source-specific identities: BC guidance uses `document_key + current_version` (or a content hash if no version is supplied); California pathways prefer a source `pathway_id`, otherwise hash company, fuel, class, and pathway description. CI and ordinary row position are excluded from a pathway's long-term identity. `source_row` is only a tie-breaker when otherwise identical records occur more than once in the same input file. This intentionally favors a visible duplicate over silently merging distinct records.

BC LCFS has a separate configured local JSON digest source at:

```text
D:\WorkSpace\Code\RegProgram_Automation\program\BC_LCFS\digest_input
```

Matching BC digests are converted locally from `document_key`, `title`, and `digest_summary` into a single `Guidance Updates` subsection under BC Low Carbon Fuel Standard (LCFS). Each heading uses `document_key — title`, so the guidance file number appears first. The subsection heading appears once, and one `View original source →` link is shown after all guidance items. The link is read from the digest's `source.source_page` field. BC local digest content is not sent to OpenAI.

The reporting period is the previous Friday at 00:00 through the current Friday at 00:00—Friday through Thursday inclusive—in `America/Regina`. The scheduled email is sent every Friday at 9:00 AM. Each digest includes a deterministic `Digest ID` in its text/HTML footer and `Message-ID` header. Before delivery, the ID and selected items are atomically recorded as a pending send transaction. If a run stops in that uncertain state, later automatic sends stop until it is explicitly resolved.

## How relevance is determined

1. Gmail returns only messages from the configured source addresses and within the reporting window.
2. Each sender maps to exactly one permitted regulatory program.
3. GPT-5 nano is told to extract only distinct items directly related to that permitted program.
4. Mixed-topic senders—CARB, Oregon DEQ, Washington Ecology, NMED, and GOV.UK—can return zero relevant items.
5. Dedicated CFR and BC LCFS senders are still summarized item-by-item.
6. New Mexico CTFP accepts both `nmed@public.govdelivery.com` and `cleanfuel.standard@env.nm.gov` as configured sources.
7. The model may select only a link that was actually extracted from the email. An invented link is rejected; the Gmail message itself is used as the fallback source.
8. Sent items are recorded in `runtime/state/state.json` and are not sent again.

All direct commands below assume you are in the project root. Examples labelled `bat` are for Windows Command Prompt, not PowerShell. The application uses a `src/` layout: setup installs dependencies, not the application package, so direct `python -m weekly_clean_fuels_digest...` calls need `PYTHONPATH` pointing to `src`. The batch runners set it automatically; in PowerShell use `$env:PYTHONPATH = Join-Path (Get-Location).Path "src"`.

For an ambiguous pending send, first check the recipient mailbox for the displayed `Digest ID`. Then resolve it without editing JSON from Command Prompt:

```bat
set "PYTHONPATH=%CD%\src"
.venv\Scripts\python.exe -m weekly_clean_fuels_digest.main --resolve-pending "wcf-PASTE-THE-EXACT-ID" --resolution sent
```

Use `--resolution sent` only after confirming delivery. If you have confirmed no message was delivered, use `--resolution not-sent` to permit a retry. Resolution never sends email by itself. Do not hand-edit `state.json`. Email item keys retain the legacy rule; local California and BC keys use their source-specific identity rules, so the first post-upgrade run may re-include previously sent local records.

Every verified clickable source in the HTML email is labeled `View original source →`. Standard email-derived items show the label on each item. The California LCFS local-pathway cluster shows it only once after both `Newly Certified Pathway(s)` and `Existing Pathway Updates` (when present), and links to CARB's `current-pathways_all.xlsx` workbook. BC guidance has its own single group-level link. Non-public local file URLs are omitted from both HTML and plain text.

## 1. Prerequisites

- Windows 10 or 11
- Python 3.11 or later
- A Google account with access to `wenli.insight@gmail.com`
- An OpenAI API key with available API credit

## 2. Create Gmail OAuth credentials

The script never stores the Gmail password. It uses Google OAuth.

1. Open Google Cloud Console.
2. Create or select a Google Cloud project.
3. Enable **Gmail API** for the project.
4. Configure the OAuth consent screen. For a personal project, add `wenli.insight@gmail.com` as a test user if the app remains in testing.
5. Create an OAuth client ID with application type **Desktop app**.
6. Download the JSON file.
7. Rename it to `credentials.json` and place it here:

   ```text
   weekly_clean_fuels_digest\runtime\secrets\credentials.json
   ```

On the first manual run, a browser window will ask you to authorize Gmail read and send access. The resulting token is stored locally as `runtime\secrets\token.json`. Never email, publish, or commit either secrets file.

Official Gmail Python quickstart: <https://developers.google.com/workspace/gmail/api/quickstart/python>

## 3. Create the OpenAI API key

1. Open the OpenAI API platform at <https://platform.openai.com/api-keys>.
2. Create an API key and ensure the API account has available credit.
3. In Windows PowerShell, save it as a user environment variable:

   ```powershell
   [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "PASTE_YOUR_KEY_HERE", "User")
   ```

4. Sign out and back in, or restart the computer, so Task Scheduler can see the new variable.

Do not put the key in `config/config.yaml` or source code.

The default model is `gpt-5-nano`, a low-cost model suited to classification and summarization. Change only `ai.model` in `config/config.yaml` if a different OpenAI model is required.

## 4. Install Python packages

Double-click:

```text
scripts\setup_windows.bat
```

It creates a local `.venv` and installs the packages from `requirements.txt`.

Create the environment at the final deployment path. After moving the project, recreate `.venv` there rather than copying it, reinstall dependencies, and rerun the tests and preview. Re-register both scheduled tasks from the new path and verify their actions and working directories. Use `.venv\Scripts\python.exe -m ...` instead of relying on a generated console launcher that may embed an old absolute path.

To run the automated tests, install the separate development dependencies:

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

## 5. Run the first preview

Double-click:

```text
scripts\run_preview.bat
```

The first run opens the Google authorization page. After authorization, the script creates:

- `runtime\output\weekly_digest_preview.html` — the formatted email preview;
- `runtime\output\weekly_digest_preview.txt` — the plain-text fallback;
- `runtime\output\weekly_digest_items.json` — all extracted items;
- `runtime\logs\weekly_digest.log` — processing log.

Preview mode does not send an email and does not mark items as processed.

You can also test a specific period from Command Prompt:

```bat
set "PYTHONPATH=%CD%\src"
.venv\Scripts\python.exe -m weekly_clean_fuels_digest.main --start 2026-09-11 --end 2026-09-18
```

The start date is inclusive. The end date is exclusive.

## 6. Test sending

After reviewing the HTML preview, run:

```bat
set "PYTHONPATH=%CD%\src"
.venv\Scripts\python.exe -m weekly_clean_fuels_digest.main --send
```

This sends the digest from and to `wenli.insight@gmail.com`, then records the included items in `runtime\state\state.json`.

To deliberately include previously sent items during a test:

```bat
set "PYTHONPATH=%CD%\src"
.venv\Scripts\python.exe -m weekly_clean_fuels_digest.main --include-processed
```

This remains preview-only unless `--send` is also supplied.

## 7. Install the Windows scheduled tasks

After the preview and send tests succeed, open PowerShell in this project directory and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install_scheduled_task.ps1
```

The installer registers or replaces both tasks:

| Task name | Runner | Windows-local trigger | Execution limit |
|---|---|---|---|
| `Weekly Clean Fuels Regulatory Digest` | `scripts\run_weekly.bat` | Friday 09:00 | 1 hour |
| `Weekly Clean Fuels Digest Watchdog` | `scripts\run_watchdog.bat` | Saturday 09:00 | 15 minutes |

Both use the project root as their working directory, `StartWhenAvailable`, and `IgnoreNew` for overlapping instances. They currently run with an interactive Windows logon, so the computer must be powered on and the user logged in. Windows trigger times use the machine's local timezone; keep it aligned with `America/Regina` for the intended send time.

The installer currently hard-codes Friday/Saturday 09:00; changing `schedule.weekday` or `schedule.time` in YAML does not update the registered triggers, and the reporting-window calculation remains Friday-based. If the schedule changes, reconcile the configuration and installer, then re-register both tasks. A correct registration alone does not prove a successful scheduled run: check Task Scheduler's last result, the application log, the corresponding send transaction, and receipt separately.

## 8. Configuration changes

Edit only `config/config.yaml` to:

- add or remove a regulatory program;
- update a sender address;
- add inclusion or exclusion guidance;
- change the model or summary language;
- change the recipient or email subject.
- add or change a local digest source.
- set `integrations.local_digest_enabled` to `false` for a Gmail-only run, or `true` to include configured local digest interfaces. The production default is `true`.
- configure independent notification channels, watchdog grace hours, and `alerts.watchdog_armed_from`.

The Python code does not need to be changed when the regulatory inventory evolves.

## Accuracy and safety controls

- The email body is explicitly treated as untrusted data to reduce prompt-injection risk.
- A sender can map to only one configured regulatory program.
- Mixed newsletters are evaluated item-by-item rather than accepted as a whole.
- The model is not asked to provide impact analysis or outside background.
- The model returns structured JSON validated by Pydantic.
- Source URLs must come from the actual email.
- Unrelated or ambiguous messages are excluded. Any analysis failure stops the run so an incomplete digest is not sent.
- The email preview and full log remain available for QA/QC.
- An unresolved or already-sent digest transaction blocks accidental repeat delivery; pending records require explicit resolution.
- Gmail and OpenAI requests use bounded timeouts; OpenAI retries and the overall 55-minute work budget stay below Task Scheduler's one-hour limit.
- `runtime/logs/weekly_digest.log` rotates at 5 MB and retains five backups by default. The three preview files use fixed names and are overwritten each run.

## Commercial maintenance standard

- Keep production code, configuration, documentation, `tests/`, `requirements.txt`, and `requirements-dev.txt` as permanent maintained project assets.
- Run the automated tests after every code, dependency, configuration-schema, or rendering change and before production deployment.
- `.github\workflows\ci.yml` runs that same offline suite on pushes to `main` or `DS-fix` and on pull-request events (Windows, Python 3.11 and 3.13). Other branch pushes alone do not trigger this workflow. It uses no Gmail access, sends no mail, needs no production key, and rejects tracked files under `runtime/secrets/`.
- Rendered email output is pinned by snapshots in `tests\fixtures\`. After a deliberate, reviewed change to the layout, regenerate them with `set UPDATE_RENDER_FIXTURES=1` before running the suite, and read the resulting diff.
- Delete generated caches and test work directories after verification; never delete `tests/` as routine cleanup.
- Review dependency upgrades before deployment and preserve reproducible dependency manifests.
- Keep all credentials outside source control and limit filesystem access to `runtime/secrets/`, state, logs, and output.
- Retain operational logs and generated reports according to an explicit business retention policy; do not treat historical logs as source configuration.
- Update `README.md`, `BUILD_SPECIFICATION.md`, and `PROJECT_PROGRESS.md` together whenever production behavior, deployment paths, integrations, or operating procedures change.

## Failure alerts and the delivery watchdog

The digest is the only thing that reports a week's regulatory activity, so a week with no email must not pass silently. Two mechanisms cover that.

**The run reports its own failure.** When the weekly run fails, the application writes `runtime\state\last_failure.json` and, in send mode, tries three notification channels that do not use Gmail:

- a message box — through `msg.exe` when it is installed, otherwise through a PowerShell message box; it needs you to be logged in, and a dialog that is not dismissed within a minute counts as unconfirmed rather than delivered;
- a date-stamped file on your Desktop, `Weekly Digest ALERT <date>.txt` — persists after a session closes and can be written without a visible session if a process is running with access to that Desktop; the current interactive scheduled tasks still require a logged-in user;
- an entry in the Windows Application event log (`eventcreate.exe`) — disabled in the production YAML, because the tested non-elevated task received `Access is denied`. The code fallback when alert settings are absent enables this channel, so retain explicit switches in deployment configuration.

Production currently enables popup and Desktop marker, and disables event log. Every channel records whether it worked, so `runtime\logs\weekly_digest.log` and the console output state which notifications the application recorded as successful; writing a Desktop marker does not prove that you read it. A failure record alone does not count as operator notification. Preview failures record evidence without requesting the popup/Desktop/event-log channels.

The application's process exit codes are `0` success, `1` a failure raised during the run (including a Gmail or OpenAI credential error), and `2` a startup failure such as a missing or invalid configuration, a missing `OPENAI_API_KEY`, or unusable state. The batch runners return `1` before Python starts if `.venv\Scripts\python.exe` is missing; that wrapper failure cannot use application alert channels.

**The watchdog checks delivery independently.** `scripts\run_watchdog.bat` runs from its own scheduled task every Saturday at 09:00. It sends no mail, does not need `OPENAI_API_KEY`, and answers one question: did the digest for the period that ended on Friday actually go out? Four rules keep that answer honest:

- A period is accounted for only if a `sent` transaction, or the legacy-compatible `last_run` record, has timezone-aware bounds ending at the expected Friday midnight and starting no later than the preceding Friday. A shorter one-off report does not mask a missing weekly digest; a longer catch-up run with the same end counts. This is a local recorded-send check, not a fresh mailbox or recipient-delivery verification.
- A period is reported only after the scheduled send time plus `alerts.grace_hours` (six hours by default), and each missed period is reported once after at least one notification channel succeeds. Six hours makes a period eligible on Friday at 15:00; with the installed Saturday 09:00 task, automatic notification occurs on Saturday, not Friday afternoon.
- If no notification channel delivers, the period is deliberately left unmarked so the next check retries. If the watchdog cannot read its own configuration or state, it alerts rather than exiting quietly.
- `alerts.watchdog_armed_from` names the earliest period end that must alert even when there is no send history at all. Production sets it to `2026-10-09`. Empty or omitted means an entirely empty history remains `uninitialized`; it does not disable missing-period checks when history exists.

Its exit codes are `0` no alert required (including an uninitialized history), `2` a configuration/state/other check failure, `3` a digest is missing or blocked (including a period already reported), and `4` a required or test alert could not be delivered through any notification channel. Configuration and unexpected check errors still attempt notification, but return `2` regardless of channel outcomes. Bookkeeping lives in `runtime\state\watchdog.json`, separate from the digest's own state. `--force-alert` deliberately repeats a period notification; `--now ISO_TIMESTAMP` and `--grace-hours HOURS` are testing overrides, and `--config PATH` selects another configuration. Overrides can issue real alerts and update watchdog bookkeeping; use them only deliberately.

Verify the channels once, before relying on them:

```bat
scripts\run_watchdog.bat --test-alert
```

This attempts a test notification through every enabled channel without sending mail or changing digest/watchdog state or `last_failure.json`. It may write the Desktop marker and append log entries. Exit `0` means at least one notification channel reported success, not that every channel worked or that the operator necessarily read a marker. Review each channel outcome. A popup timeout is always unconfirmed and uses no shared display-proof file.

Limitation: the watchdog runs on the same computer as the digest. If the computer is off, or nobody is logged in, for a whole period, no local check can report it; that case would need an off-machine heartbeat.

## Troubleshooting

### `OPENAI_API_KEY is not set`

Set the user environment variable, then sign out and back in. Check presence in a new Command Prompt without printing the secret:

```bat
if defined OPENAI_API_KEY (echo OPENAI_API_KEY is set) else (echo OPENAI_API_KEY is missing)
```

This checks only presence, not validity or API credit. Never print the key into screenshots or support messages.

### Google says the app is not verified

Confirm that the OAuth consent screen is configured and that `wenli.insight@gmail.com` is listed as a test user. For a personal desktop automation, the app does not need public publication.

### Gmail authorization scopes changed

Delete `runtime\secrets\token.json` and run `scripts\run_preview.bat` again to obtain a new token with the configured scopes.

### The scheduled task runs but no email arrives

Check:

```text
runtime\logs\weekly_digest.log
```

Also confirm that both task actions and working directories point to the current deployment, that the task can access the user-level `OPENAI_API_KEY`, and that the computer was online. Compare the last task result with the log and period-specific transaction: a later successful manual send does not prove an earlier scheduled invocation exited successfully. Since the run reports its own failures, also check `runtime\state\last_failure.json` and your Desktop for `Weekly Digest ALERT *.txt`. If neither exists and no alert appeared, run `scripts\run_watchdog.bat` to see what the watchdog concludes.

### A relevant item was missed

Add the exact terminology to that program's `include_terms` list in `config/config.yaml`, retain the source email, and rerun preview mode for the same period with explicit `--start` and `--end` dates.

### An unrelated item was included

Add the unrelated topic to the program's `exclude_terms` list. The exclusion list is guidance to the classifier; the target program name remains the primary criterion.
