#!/bin/bash

# Constants
HOTSPOT_PASSWORD="REPLACE_ME"

# set the directory
cd ~/

echo "HealthTRAC Hub Setup"

echo "Updating APT packages:"
sudo apt update
sudo apt upgrade -y

echo "Installing required APT packages"
sudo apt install -y btop git neovim tmux
sudo apt install -y chrony liblgpio-dev python3-dev swig

echo "Cloning project repository"
git clone "https://github.com/hudakdesign/healthTRAC"
cd healthTRAC
# for now switch to the development branch too
git fetch origin development
git checkout development

echo "Creating python environment"
python -m venv .venv
source .venv/bin/activate

echo "Installing required PIP packages"
pip install -r requirements.txt

echo "Setting up systemd service"
sudo cp /home/healthtrac/healthTRAC/setup/healthtrac_hub.service /lib/systemd/system/healthtrac_hub.service
sudo chmod 644 /lib/systemd/system/healthtrac_hub.service
sudo systemctl daemon-reload
sudo systemctl enable healthtrac_hub.service
sudo systemctl start healthtrac_hub.service

echo "Setting up hotspot"
INTERFACE_NAME="wlan1"
SSID="HealthTRAC-Hub"
CON_NAME=$SSID
sudo nmcli device wifi hotspot ifname $INTERFACE_NAME con-name $CON_NAME ssid $SSID password $HOTSPOT_PASSWORD
sudo nmcli con mod $CON_NAME autoconnect yes

echo "DONE!"