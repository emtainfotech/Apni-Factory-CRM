# Register Windows Daily 6:00 AM Cron Task for Morning WhatsApp Report
$morningBat = "e:\APNI FACTORY\ApniFactoryCRM\scripts\cron_send_morning_report.bat"
$morningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$morningBat`""
$morningTrigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
Register-ScheduledTask -TaskName "ApniFactory_Morning_WhatsApp_Report" -Action $morningAction -Trigger $morningTrigger -Description "Apni Factory CRM Daily 6:00 AM WhatsApp Dashboard Report" -Force
Write-Host "Scheduled task 'ApniFactory_Morning_WhatsApp_Report' successfully registered for 6:00 AM daily."

# Register Windows Daily 8:00 PM Cron Task for Evening WhatsApp Report
$eveningBat = "e:\APNI FACTORY\ApniFactoryCRM\scripts\cron_send_evening_report.bat"
$eveningAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$eveningBat`""
$eveningTrigger = New-ScheduledTaskTrigger -Daily -At 8:00PM
Register-ScheduledTask -TaskName "ApniFactory_Evening_WhatsApp_Report" -Action $eveningAction -Trigger $eveningTrigger -Description "Apni Factory CRM Daily 8:00 PM WhatsApp Dashboard Report" -Force
Write-Host "Scheduled task 'ApniFactory_Evening_WhatsApp_Report' successfully registered for 8:00 PM daily."
