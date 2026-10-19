#!/usr/bin/env bash
# ==============================================================================
# Apni Factory CRM — Automated WhatsApp Morning Report Cron Runner (6:00 AM IST)
# Server Path: /var/www/apnifactory-crm
# ==============================================================================

# Determine project directory
if [ -d "/var/www/apnifactory-crm" ]; then
    PROJECT_DIR="/var/www/apnifactory-crm"
else
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

cd "$PROJECT_DIR" || exit 1

# Setup log file (fallback to /tmp if project directory is not writable)
LOG_FILE="$PROJECT_DIR/whatsapp_morning_report.log"
if ! touch "$LOG_FILE" 2>/dev/null; then
    LOG_FILE="/tmp/whatsapp_morning_report.log"
fi

{
    echo "================================================================================"
    echo ">>> WhatsApp Morning Report Runner Started at: $(date)"
    echo ">>> Running as user: $(whoami)"
    echo ">>> Working directory: $PROJECT_DIR"

    # Locate Python interpreter inside virtual environment directly
    PYTHON_BIN=""
    for candidate in \
        "$PROJECT_DIR/myenv/bin/python" \
        "$PROJECT_DIR/venv/bin/python" \
        "$PROJECT_DIR/env/bin/python" \
        "$PROJECT_DIR/.venv/bin/python" \
        "/var/www/apnifactory-crm/myenv/bin/python" \
        "/var/www/apnifactory-crm/venv/bin/python" \
        "/var/www/apnifactory-crm/env/bin/python" \
        "/var/www/apnifactory-crm/.venv/bin/python"
    do
        if [ -x "$candidate" ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    done

    # Fallback to system python3/python if virtualenv not found at standard path
    if [ -z "$PYTHON_BIN" ]; then
        if command -v python3 >/dev/null 2>&1; then
            PYTHON_BIN="$(command -v python3)"
        elif command -v python >/dev/null 2>&1; then
            PYTHON_BIN="$(command -v python)"
        fi
    fi

    if [ -z "$PYTHON_BIN" ]; then
        echo "ERROR: Could not find Python interpreter!" >&2
        exit 1
    fi

    echo ">>> Using Python interpreter: $PYTHON_BIN"
    "$PYTHON_BIN" -V

    # Run the management command (Morning report)
    "$PYTHON_BIN" manage.py send_morning_report --type morning
    EXIT_CODE=$?

    echo ">>> Finished with exit code: $EXIT_CODE at: $(date)"
    echo "================================================================================"
} >> "$LOG_FILE" 2>&1

exit 0
