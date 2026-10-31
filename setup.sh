#!/usr/bin/env bash
set -e

echo "====================================================="
echo " BUSY Bar + Google Home Laundry Bridge Setup "
echo "====================================================="

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "Installing python3 and python3-venv..."
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv
fi

# Ensure venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment & installing requirements..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "Creating .env configuration file from template..."
    cp .env.example .env
    echo "IMPORTANT: Please edit .env with your BUSY Bar IP and Sinric Pro credentials:"
    echo "  nano .env"
fi

# Systemd service setup prompt
read -p "Do you want to install and enable the background systemd service now? (y/n): " INSTALL_SERVICE
if [[ "$INSTALL_SERVICE" =~ ^[Yy]$ ]]; then
    CURRENT_USER=$(whoami)
    CURRENT_DIR=$(pwd)

    echo "Configuring busy-laundry.service for user '$CURRENT_USER' in '$CURRENT_DIR'..."
    sed -i "s|User=pi|User=$CURRENT_USER|g" busy-laundry.service
    sed -i "s|/home/pi/busy-laundry|$CURRENT_DIR|g" busy-laundry.service

    sudo cp busy-laundry.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable busy-laundry.service
    sudo systemctl restart busy-laundry.service
    echo "Service installed and started!"
    echo "Check status with: sudo systemctl status busy-laundry.service"
fi

echo "====================================================="
echo " Setup complete! "
echo " Test with: ./venv/bin/python laundry_bridge.py --test"
echo "====================================================="
