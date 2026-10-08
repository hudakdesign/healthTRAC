#!/bin/bash

# Constants
NETWORK_NAME="netplan-wlan0-HealthTRAC-Hub"
STATIC_IP_ADDRESS="10.42.0.103/24"

# set directory
cd ~/

echo "HealthTRAC Satellite Setup"

# set up static ip
echo "Configuring static IP"
sudo nmcli con mod $NETWORK_NAME ipv4.method manual ipv4.addr "$STATIC_IP_ADDRESS"

# run updates
echo "Updating APT packages"
sudo apt update
sudo apt upgrade -y

# install apt reqs
echo "Installing required APT packages"
sudo apt install -y btop git neovim tmux

# clone the project
echo "Cloning project repository"
git clone "https://github.com/hudakdesign/healthTRAC"
cd healthTRAC
# for now switch to the development branch too
git fetch origin development
git checkout development

# create python env
echo "Creating python environment"
python -m venv .venv
source .venv/bin/activate

# install pip reqs
echo "Installing required PIP packages"
pip install -r requirements.txt

echo "DONE!"