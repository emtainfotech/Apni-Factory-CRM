#!/usr/bin/env bash
# ==============================================================================
# Apni Factory CRM — Automated WhatsApp Morning Report Cron Runner
# Server Path: /var/www/apnifactory-crm
# ==============================================================================

# Project directory on server
if [ -d "/var/www/apnifactory-crm" ]; then
    PROJECT_DIR="/var/www/apnifactory-crm"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJECT_DIR" || exit 1

# Activate virtual environment
if [ -f "$PROJECT_DIR/myenv/bin/activate" ]; then
    source "$PROJECT_DIR/myenv/bin/activate"
elif [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
elif [ -f "myenv/bin/activate" ]; then
    source "myenv/bin/activate"
fi

# Run the morning report (sends today's live metrics to all registered admin WhatsApp numbers)
python manage.py send_morning_report >> "$PROJECT_DIR/whatsapp_morning_report.log" 2>&1
