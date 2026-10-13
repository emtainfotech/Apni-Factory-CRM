@echo off
:: ==============================================================================
:: Apni Factory CRM — Automated WhatsApp Evening Report Runner (Windows)
:: ==============================================================================

cd /d "e:\APNI FACTORY\ApniFactoryCRM"

if exist "e:\APNI FACTORY\ApniFactoryCRM\myenv\Scripts\python.exe" (
    "e:\APNI FACTORY\ApniFactoryCRM\myenv\Scripts\python.exe" manage.py send_morning_report --type evening >> "e:\APNI FACTORY\ApniFactoryCRM\whatsapp_evening_report.log" 2>&1
) else (
    python manage.py send_morning_report --type evening >> "e:\APNI FACTORY\ApniFactoryCRM\whatsapp_evening_report.log" 2>&1
)
