#!/bin/bash

# set the directory
cd ~/

echo "HealthTRAC Setup"

echo "Updating APT packages:"
sudo apt update
sudo apt upgrade -y

echo "Installing required APT packages"
sudo apt install -y btop git neovim tmux
sudo apt install -y liblgpio-dev python3-dev swig

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

echo "DONE!"