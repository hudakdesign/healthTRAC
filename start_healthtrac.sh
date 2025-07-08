#!/bin/bash
# HealthTRAC System Startup Script
# Starts all components for testing

# Configuration
HUB_HOST = "localhost"  # Change to Ubuntu VM IP in production
HUB_PORT = 5555

# Colors for output
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

echo
"=========================================="
echo
" HealthTRAC System Startup"
echo
"=========================================="
echo
""

# Function to check if a process is running
check_process()
{
if pgrep - f
"$1" > / dev / null;
then
return 0
else
return 1
fi
}

# Start hub server
echo - e
"${YELLOW}Starting Hub Server...${NC}"
if check_process
"hub_server.py";
then
echo - e
"${GREEN}✓ Hub server already running${NC}"
else
python
hub_server.py &
HUB_PID =$!
sleep
2
if check_process
"hub_server.py";
then
echo - e
"${GREEN}✓ Hub server started (PID: $HUB_PID)${NC}"
else
echo - e
"${RED}✗ Failed to start hub server${NC}"
exit
1
fi
fi

echo
""

# Function to start a sensor client
start_sensor()
{
local
sensor_name =$1
local
script_name =$2
local
extra_args =$3

echo - e
"${YELLOW}Starting $sensor_name...${NC}"
if check_process "$script_name"; then
echo - e
"${GREEN}✓ $sensor_name already running${NC}"
else
python $script_name - -hub - host $HUB_HOST - -hub - port $HUB_PORT $extra_args &
local
pid =$!
sleep
2
if check_process "$script_name"; then
echo - e
"${GREEN}✓ $sensor_name started (PID: $pid)${NC}"
else
echo - e
"${RED}✗ Failed to start $sensor_name${NC}"
echo
"  Check if hardware is connected"
fi
fi
}

# Start sensor clients
start_sensor
"FSR Sensor" "fsr_client.py" ""
echo
""

start_sensor
"Accelerometer" "accelerometer_client.py" ""
echo
""

start_sensor
"Microphone (simulated)" "microphone_client.py" ""
echo
""

# Start dashboard
echo - e
"${YELLOW}Starting Dashboard...${NC}"
if check_process
"dashboard_viewer.py";
then
echo - e
"${GREEN}✓ Dashboard already running${NC}"
else
# Start dashboard in new terminal if possible
if command - v gnome-terminal & > / dev / null; then
gnome-terminal -- python dashboard_viewer.py --hub-host $HUB_HOST
echo -e "${GREEN}✓ Dashboard started in new terminal${NC}"
elif command -v xterm & > / dev / null; then
xterm -e python dashboard_viewer.py --hub-host $HUB_HOST &
echo -e "${GREEN}✓ Dashboard started in new terminal${NC}"
else
python dashboard_viewer.py --hub-host $HUB_HOST &
echo -e "${GREEN}✓ Dashboard started (PID: $!)${NC}"
fi
fi

echo ""
echo "=========================================="
echo -e "${GREEN}HealthTRAC System Started${NC}"
echo "=========================================="
echo ""
echo "Hub server: http://$HUB_HOST:$HUB_PORT"
echo "Data files: ./data/"
echo ""
echo "To stop all components:"
echo "  ./stop_healthtrac.sh"
echo ""
echo "To view logs:"
echo "  tail -f ./data/*/session_metadata.json"
echo ""