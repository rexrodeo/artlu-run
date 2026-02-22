#!/bin/bash
# OpenClaw Health Monitor for ARTLU.RUN Production

# Load environment
if [[ -f ".env" ]]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

OPENCLAW_URL="${OPENCLAW_GATEWAY_URL:-http://localhost:18789}"
LOG_FILE="/tmp/artlu-openclaw-monitor.log"
ALERT_EMAIL="${ADMIN_EMAIL:-vonrexroad@gmail.com}"

# Function to log with timestamp
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Function to send alert (requires mail command)
send_alert() {
    local message="$1"
    log "ALERT: $message"
    
    # Try to send email if mail command is available
    if command -v mail &> /dev/null; then
        echo "$message" | mail -s "ARTLU OpenClaw Alert" "$ALERT_EMAIL" 2>/dev/null || true
    fi
    
    # Could add Slack/Discord webhook here for alerts
}

# Check OpenClaw health
check_openclaw() {
    if curl -s -f --max-time 10 "$OPENCLAW_URL/health" >/dev/null 2>&1; then
        log "✅ OpenClaw healthy at $OPENCLAW_URL"
        return 0
    else
        log "❌ OpenClaw unreachable at $OPENCLAW_URL"
        return 1
    fi
}

# Check disk space
check_disk() {
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $DISK_USAGE -gt 90 ]]; then
        send_alert "Disk usage high: ${DISK_USAGE}%"
        return 1
    else
        log "✅ Disk usage OK: ${DISK_USAGE}%"
        return 0
    fi
}

# Check memory usage
check_memory() {
    MEMORY_USAGE=$(ps aux | awk '/openclaw/ && !/awk/ {sum+=$4} END {print int(sum)}')
    if [[ $MEMORY_USAGE -gt 50 ]]; then
        log "⚠️  OpenClaw memory usage: ${MEMORY_USAGE}%"
    else
        log "✅ OpenClaw memory usage OK: ${MEMORY_USAGE}%"
    fi
}

# Main monitoring loop
main() {
    log "🔍 Starting OpenClaw health check"
    
    local failed=0
    
    # Run checks
    check_openclaw || ((failed++))
    check_disk || ((failed++))
    check_memory
    
    # Summary
    if [[ $failed -eq 0 ]]; then
        log "✅ All systems healthy"
    else
        send_alert "OpenClaw monitoring detected $failed issues. Check logs: $LOG_FILE"
    fi
    
    log "🔍 Health check complete"
    echo ""
}

# If running as script (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi