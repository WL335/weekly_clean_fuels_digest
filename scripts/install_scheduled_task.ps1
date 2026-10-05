$ErrorActionPreference = "Stop"
$ScriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDirectory = Split-Path -Parent $ScriptsDirectory
$Runner = Join-Path $ScriptsDirectory "run_weekly.bat"
$WatchdogRunner = Join-Path $ScriptsDirectory "run_watchdog.bat"
$TaskName = "Weekly Clean Fuels Regulatory Digest"
$WatchdogTaskName = "Weekly Clean Fuels Digest Watchdog"

foreach ($path in @($Runner, $WatchdogRunner)) {
    if (-not (Test-Path $path)) {
        throw "Runner not found: $path"
    }
}

$Action = New-ScheduledTaskAction `
    -Execute "$env:SystemRoot\System32\cmd.exe" `
    -Argument "/c `"$Runner`"" `
    -WorkingDirectory $ProjectDirectory

$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 9:00AM
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Summarize clean-fuels regulatory subscription emails from the prior Friday through Thursday." `
    -Force

# Delivery watchdog. Keep it in its own task: a failure inside the digest task
# must not be able to stop the check, and it must run without the OpenAI key.
$WatchdogAction = New-ScheduledTaskAction `
    -Execute "$env:SystemRoot\System32\cmd.exe" `
    -Argument "/c `"$WatchdogRunner`"" `
    -WorkingDirectory $ProjectDirectory

$WatchdogTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 9:00AM
$WatchdogSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $WatchdogTaskName `
    -Action $WatchdogAction `
    -Trigger $WatchdogTrigger `
    -Settings $WatchdogSettings `
    -Description "Alert when the weekly clean-fuels digest for the expected period was never delivered." `
    -Force

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Schedule: every Friday at 9:00 AM (Windows local time)"
Write-Host "Scheduled task installed: $WatchdogTaskName"
Write-Host "Schedule: every Saturday at 9:00 AM local time (delivery watchdog)"
Write-Host "Run the preview manually and complete Gmail authorization before relying on the task."
Write-Host "Verify the alert channels once with: scripts\run_watchdog.bat --test-alert"
