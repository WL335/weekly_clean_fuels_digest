$ErrorActionPreference = "Stop"
$ScriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDirectory = Split-Path -Parent $ScriptsDirectory
$Runner = Join-Path $ScriptsDirectory "run_weekly.bat"
$TaskName = "Weekly Clean Fuels Regulatory Digest"

if (-not (Test-Path $Runner)) {
    throw "Runner not found: $Runner"
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

Write-Host "Scheduled task installed: $TaskName"
Write-Host "Schedule: every Friday at 9:00 AM (Windows local time)"
Write-Host "Run the preview manually and complete Gmail authorization before relying on the task."

