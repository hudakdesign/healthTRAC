#!/bin/bash
# HealthTRAC System Stop Script
# Stops all running components

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo " HealthTRAC System Shutdown"
echo "=========================================="
echo ""

# Function to stop a process
stop_process() {
    local process_name=$1
    local display_name=$2

    echo -e "${YELLOW}Stopping $display_name...${NC}"

    if pgrep -f "$process_name" > /dev/null; then
        pkill -f "$process_name"
        sleep 1

        if pgrep -f "$process_name" > /dev/null; then
            echo -e "${RED}✗ Failed to stop $display_name (trying force kill)${NC}"
            pkill -9 -f "$process_name"
            sleep 1
        fi

        if pgrep -f "$process_name" > /dev/null; then
            echo -e "${RED}✗ Could not stop $display_name${NC}"
        else
            echo -e "${GREEN}✓ $display_name stopped${NC}"
        fi
    else
        echo -e "${GREEN}✓ $display_name not running${NC}"
    fi
}

# Stop all components
stop_process "dashboard_viewer.py" "Dashboard"
echo ""

stop_process "microphone_client.py" "Microphone Client"
echo ""

stop_process "accelerometer_client.py" "Accelerometer Client"
echo ""

stop_process "fsr_client.py" "FSR Client"
echo ""

# Stop hub server last to allow clients to disconnect gracefully
stop_process "hub_server.py" "Hub Server"
echo ""

echo "=========================================="
echo -e "${GREEN}HealthTRAC System Stopped${NC}"
echo "=========================================="
echo ""

# Check if any processes are still running
if pgrep -f "hub_server\|fsr_client\|accelerometer_client\|microphone_client\|dashboard_viewer" > /dev/null; then
    echo -e "${YELLOW}Warning: Some processes may still be running:${NC}"
    ps aux | grep -E "hub_server|fsr_client|accelerometer_client|microphone_client|dashboard_viewer" | grep -v grep
else
    echo "All HealthTRAC processes have been stopped."
fi
echo ""