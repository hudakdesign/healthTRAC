#!/bin/bash
# Start HealthTRAC Smart Logging System
# Coordinates hub, FSR, and MetaMotion logger components

# Configuration
HUB_HOST="localhost"  # Change to VM IP if running remotely
HUB_PORT=5555
METAMOTION_MAC="C8:0B:FB:24:C1:65"
FSR_PORT="/dev/ttyUSB0"
SYNC_HOURS=8

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "=========================================="
echo " HealthTRAC Smart Logging System"
echo "=========================================="
echo ""

# Function to check if process is running
check_process() {
    if pgrep -f "$1" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# 1. Start Hub Server
echo -e "${YELLOW}Starting Hub Server...${NC}"
if check_process "hub_server.py"; then
    echo -e "${GREEN}✓ Hub server already running${NC}"
else
    python3 hub_server.py &
    HUB_PID=$!
    sleep 2
    if check_process "hub_server.py"; then
        echo -e "${GREEN}✓ Hub server started (PID: $HUB_PID)${NC}"
    else
        echo -e "${RED}✗ Failed to start hub server${NC}"
        exit 1
    fi
fi

echo ""

# 2. Start FSR Client
echo -e "${YELLOW}Starting FSR Sensor...${NC}"
if [ -e "$FSR_PORT" ]; then
    if check_process "fsr_client.py"; then
        echo -e "${GREEN}✓ FSR client already running${NC}"
    else
        python3 fsr_client.py --serial-port $FSR_PORT --hub-host $HUB_HOST &
        FSR_PID=$!
        sleep 2
        if check_process "fsr_client.py"; then
            echo -e "${GREEN}✓ FSR client started (PID: $FSR_PID)${NC}"
        else
            echo -e "${RED}✗ Failed to start FSR client${NC}"
        fi
    fi
else
    echo -e "${YELLOW}⚠ FSR not connected at $FSR_PORT${NC}"
fi

echo ""

# 3. Check MetaMotion Configuration
echo -e "${YELLOW}Checking MetaMotion configuration...${NC}"
echo "Has the MetaMotion been configured for smart logging? (y/n)"
read -r configured

if [ "$configured" != "y" ]; then
    echo -e "${YELLOW}Configuring MetaMotion for smart logging...${NC}"
    python3 configure_smart_logging.py $METAMOTION_MAC

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Configuration complete${NC}"
    else
        echo -e "${RED}✗ Configuration failed${NC}"
        echo "Please check BLE connection and try again"
        exit 1
    fi
fi

echo ""

# 4. Start MetaMotion Logger
echo -e "${YELLOW}Starting MetaMotion Logger...${NC}"
if check_process "metamotion_logger.py"; then
    echo -e "${GREEN}✓ MetaMotion logger already running${NC}"
else
    python3 metamotion_logger.py \
        --mac-address $METAMOTION_MAC \
        --hub-host $HUB_HOST \
        --sync-hours $SYNC_HOURS &
    MM_PID=$!
    sleep 2
    if check_process "metamotion_logger.py"; then
        echo -e "${GREEN}✓ MetaMotion logger started (PID: $MM_PID)${NC}"
        echo "  Sync interval: $SYNC_HOURS hours"
    else
        echo -e "${RED}✗ Failed to start MetaMotion logger${NC}"
    fi
fi

echo ""

# 5. Arduino Bridge Status
echo -e "${YELLOW}Arduino Bridge Status:${NC}"
echo "Is the Arduino ESP32 bridge deployed near the toothbrush dock? (y/n)"
read -r bridge_deployed

if [ "$bridge_deployed" = "y" ]; then
    echo -e "${GREEN}✓ Bridge deployed${NC}"
    echo "  The bridge will automatically sync when toothbrush is docked"
else
    echo -e "${YELLOW}⚠ Deploy Arduino bridge for automatic sync${NC}"
    echo "  1. Upload smart_dock_bridge.ino to ESP32"
    echo "  2. Configure WiFi credentials in code"
    echo "  3. Place within 1-2 feet of toothbrush dock"
fi

echo ""

# 6. Summary
echo "=========================================="
echo -e "${GREEN}Smart Logging System Status${NC}"
echo "=========================================="
echo ""
echo "Hub Server:     http://$HUB_HOST:$HUB_PORT"
echo "Data Directory: ./data/"
echo ""
echo "Battery Optimization Active:"
echo "- Motion threshold: 0.1g"
echo "- Dock detection: 30 minutes"
echo "- BLE duty cycle: <1%"
echo "- Expected battery: 11+ days"
echo ""
echo "To monitor:"
echo "  python3 dashboard_viewer.py --hub-host $HUB_HOST"
echo ""
echo "To stop all:"
echo "  ./stop_healthtrac.sh"
echo ""
echo -e "${GREEN}System ready for data collection!${NC}"