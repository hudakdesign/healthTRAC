#!/bin/bash
# HealthTRAC Smart Logging System Startup
# Coordinates all components for battery-optimized operation

# Configuration
HUB_HOST="localhost"  # Change to VM IP if running remotely
HUB_PORT=5555
METAMOTION_MAC="C8:0B:FB:24:C1:65"
FSR_PORT="/dev/ttyUSB0"  # Update based on your system

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=========================================="
echo " HealthTRAC Smart Logging System"
echo "==========================================${NC}"
echo ""

# Function to check if process is running
check_process() {
    if pgrep -f "$1" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to get VM IP
get_vm_ip() {
    hostname -I | awk '{print $1}'
}

# 1. System check
echo -e "${YELLOW}Performing system check...${NC}"

# Check Python dependencies
echo -n "Checking Python modules... "
python3 -c "import ntplib, serial, bleak, yaml" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo "Please install required modules: pip install ntplib pyserial bleak pyyaml"
    exit 1
fi

# Show network info
VM_IP=$(get_vm_ip)
echo -e "VM IP Address: ${GREEN}$VM_IP${NC}"
echo ""

# 2. Start Hub Server
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

# 3. Check MetaMotion Configuration
echo -e "${YELLOW}MetaMotion Configuration Check${NC}"
echo "The MetaMotion must be configured for smart logging mode."
echo "This enables motion-triggered logging and 30-minute dock detection."
echo ""
read -p "Has the MetaMotion been configured? (y/n): " configured

if [ "$configured" != "y" ]; then
    echo ""
    echo -e "${YELLOW}Select configuration mode:${NC}"
    echo "1) Test mode (1 minute dock timer)"
    echo "2) Production mode (30 minute dock timer)"
    read -p "Enter choice (1/2): " mode_choice

    if [ "$mode_choice" = "1" ]; then
        MODE="test"
        echo -e "${YELLOW}Configuring for TEST mode...${NC}"
    else
        MODE="prod"
        echo -e "${YELLOW}Configuring for PRODUCTION mode...${NC}"
    fi

    # Note: Assuming configure_smart_logging_testmode.py exists
    if [ -f "configure_smart_logging_testmode.py" ]; then
        python3 configure_smart_logging_testmode.py $METAMOTION_MAC $MODE
    elif [ -f "configure_smart_logging.py" ]; then
        python3 configure_smart_logging.py $METAMOTION_MAC
    else
        echo -e "${RED}Configuration script not found!${NC}"
        echo "Please ensure configure_smart_logging.py or configure_smart_logging_testmode.py is present"
        exit 1
    fi

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Configuration complete${NC}"
    else
        echo -e "${RED}✗ Configuration failed${NC}"
        echo "Please check BLE connection and try again"
        exit 1
    fi
fi

echo ""

# 4. Start FSR Client (if connected)
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
            echo "Check serial port connection"
        fi
    fi
else
    echo -e "${YELLOW}⚠ No FSR device at $FSR_PORT${NC}"
    echo "FSR sensor not connected or wrong port"
fi

echo ""

# 5. Start MetaMotion Smart Logger
echo -e "${YELLOW}Starting MetaMotion Smart Logger...${NC}"
if check_process "metamotion_smart_logger.py"; then
    echo -e "${GREEN}✓ MetaMotion logger already running${NC}"
else
    python3 metamotion_smart_logger.py \
        --mac-address $METAMOTION_MAC \
        --hub-host $HUB_HOST \
        --scan-interval 30 &
    MM_PID=$!
    sleep 2
    if check_process "metamotion_smart_logger.py"; then
        echo -e "${GREEN}✓ MetaMotion logger started (PID: $MM_PID)${NC}"
    else
        echo -e "${RED}✗ Failed to start MetaMotion logger${NC}"
    fi
fi

echo ""

# 6. Arduino Bridge Instructions
echo -e "${YELLOW}Arduino ESP32 Bridge Setup${NC}"
echo "The Arduino bridge handles proximity detection and data sync."
echo ""
echo "To deploy the bridge:"
echo "1. Update WiFi credentials in smart_dock_bridge.ino"
echo "2. Set HUB_HOST = \"$VM_IP\""
echo "3. Upload to ESP32"
echo "4. Place within 1-2 feet of toothbrush dock"
echo ""
echo "The bridge will:"
echo "- Detect docking via RSSI > -55dBm"
echo "- Wait for BLE advertisement (30 min after docking)"
echo "- Download and forward data to hub"
echo "- Return to low-power scanning"

echo ""

# 7. System Summary
echo -e "${BLUE}=========================================="
echo " System Status Summary"
echo "==========================================${NC}"
echo ""
echo -e "Hub Server:       ${GREEN}Running${NC} at $HUB_HOST:$HUB_PORT"
echo -e "Data Directory:   ./data/"
echo -e "FSR Sensor:       $(check_process "fsr_client.py" && echo -e "${GREEN}Active${NC}" || echo -e "${YELLOW}Not connected${NC}")"
echo -e "MetaMotion:       $(check_process "metamotion_smart_logger.py" && echo -e "${GREEN}Monitoring${NC}" || echo -e "${RED}Not running${NC}")"
echo ""
echo -e "${GREEN}Battery Optimization Active:${NC}"
echo "- Motion threshold: 0.1g"
echo "- Dock timer: 30 minutes (or 1 min in test mode)"
echo "- BLE duty cycle: <1%"
echo "- Expected battery: 11+ days"
echo ""
echo "To monitor system:"
echo "  python3 dashboard_viewer.py --hub-host $HUB_HOST"
echo ""
echo "To view logs:"
echo "  tail -f ./data/*/accelerometer_data.csv"
echo ""
echo "To stop all components:"
echo "  ./stop_healthtrac.sh"
echo ""
echo -e "${GREEN}Smart logging system ready!${NC}"
echo "The toothbrush will log data during use and sync 30 minutes after docking."