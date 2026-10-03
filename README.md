# 🧺 BUSY Bar + Google Home Laundry Bridge

An automated smart bridge for your **Raspberry Pi 3** that connects **Google Home Voice/Routine Timers** to your **BUSY Bar** (by the makers of Flipper Zero).

When your Google Home laundry timer expires, the BUSY Bar's front 72×16 RGB LED matrix immediately alerts you with:
- **`ROTATE DRYER`** (when washing is complete)
- **`FOLD LAUNDRY`** (when drying is complete)

---

## Architecture Overview

```
"Hey Google, start wash cycle"
             │
   (45-minute routine timer)
             │
             ▼
Google Home turns ON virtual switch "Washer Alert"
             │ (Instant local/cloud event)
             ▼
Raspberry Pi 3 (running laundry_bridge.py daemon)
             │ (Local HTTP API to BUSY Bar)
             ▼
BUSY Bar Matrix: "ROTATE DRYER"
```

---

## 🛠️ Step 1: Set Up Your Raspberry Pi 3 CanaKit

1. **Unbox your CanaKit:** Take out the Raspberry Pi 3, the power supply, and the included microSD card (with USB card reader).
2. **Download Raspberry Pi Imager:** On your PC/Mac, install [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
3. **Flash the OS:**
   - **Device:** Select **Raspberry Pi 3**.
   - **Operating System:** Choose **Raspberry Pi OS Lite (64-bit)** (headless, no desktop needed).
   - **Storage:** Select your microSD card.
4. **Configure Settings (Gear icon / OS Customization):**
   - Set hostname: `laundrypi` (or whatever you prefer).
   - Set username & password: e.g., `pi` and your password.
   - Configure wireless LAN: Enter your home Wi-Fi SSID and password.
   - **Enable SSH** using password authentication.
5. Click **Write**. Once complete, insert the microSD card into the Pi 3 and plug in the power supply.
6. From your computer's terminal / PowerShell, connect to the Pi:
   ```bash
   ssh pi@laundrypi.local
   ```

---

## ☁️ Step 2: Create Virtual Switches in Sinric Pro (Free)

Sinric Pro provides free virtual smart switches that Google Home recognizes natively.

1. Sign up for a free account at **[portal.sinric.pro](https://portal.sinric.pro/)**.
2. Go to **Devices** $\rightarrow$ Click **Add Device**:
   - **Device Type:** Switch
   - **Device Name:** `Washer Alert`
3. Add a second device:
   - **Device Type:** Switch
   - **Device Name:** `Dryer Alert`
4. Copy the following values from the portal:
   - **App Key** and **App Secret** (from the *Credentials* tab)
   - **Device ID** for `Washer Alert`
   - **Device ID** for `Dryer Alert`

---

## 📱 Step 3: Link Sinric Pro to Google Home

1. Open the **Google Home** app on your phone.
2. Tap **+ (Add)** $\rightarrow$ **Works with Google**.
3. Search for **Sinric Pro** and sign in with your Sinric Pro credentials.
4. Both **"Washer Alert"** and **"Dryer Alert"** will appear as smart switches in your Google Home device list!

---

## ⏱️ Step 4: Configure Your Google Home Laundry Routines

Update (or create) your voice-activated laundry automations in Google Home:

### Wash Routine:
- **Starter (Voice Command):** *"Hey Google, wash started"* or *"Start wash timer"*
- **Action 1 (Delay):** Delay start for **45 minutes** (or your machine's cycle time).
- **Action 2 (Device Control):** Turn **ON** `Washer Alert`.
- *(Optional Action 3):* Broadcast on Nest speakers: *"The wash is finished, time to rotate to the dryer."*

### Dry Routine:
- **Starter (Voice Command):** *"Hey Google, dryer started"* or *"Start dryer timer"*
- **Action 1 (Delay):** Delay start for **55 minutes**.
- **Action 2 (Device Control):** Turn **ON** `Dryer Alert`.
- *(Optional Action 3):* Broadcast on Nest speakers: *"Dryer cycle complete, please fold the laundry."*

---

## 🚀 Step 5: Install & Run on the Raspberry Pi

1. **Find your BUSY Bar IP address:**
   On your BUSY Bar, go to `Settings` $\rightarrow$ `Wi-Fi` (or check your home router) and note its IP (e.g. `192.168.1.150`).

2. **Clone or copy this project to your Pi:**
   ```bash
   mkdir -p ~/busy-laundry
   cd ~/busy-laundry
   ```
   *(Copy the files from this directory to `~/busy-laundry`)*

3. **Run the automated setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

4. **Edit your `.env` configuration:**
   ```bash
   nano .env
   ```
   Fill in your BUSY Bar IP and Sinric Pro credentials:
   ```env
   BUSY_BAR_IP=192.168.1.150
   SINRIC_APP_KEY=your_key_here
   SINRIC_APP_SECRET=your_secret_here
   # Option 1: Unified switch (recommended)
   LAUNDRY_DEVICE_ID=your_laundry_device_id
   # Option 2: Separate switches
   # WASHER_DEVICE_ID=your_washer_device_id
   # DRYER_DEVICE_ID=your_dryer_device_id
   LAUNDRY_ALERT_TEXT=Laundry done
   ALERT_SOUND=event
   ALERT_TIMEOUT_SECONDS=1800
   ```

5. **Test the display immediately:**
   ```bash
   # Test the unified laundry notification (with checkmark and sound)
   ./venv/bin/python laundry_bridge.py --test

   # Test washer or dryer alerts specifically
   ./venv/bin/python laundry_bridge.py --test-washer
   ./venv/bin/python laundry_bridge.py --test-dryer

   # Clear the screen
   ./venv/bin/python laundry_bridge.py --clear
   ```

6. **Start the background service:**
   If you didn't install the systemd service during `./setup.sh`:
   ```bash
   sudo cp busy-laundry.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now busy-laundry.service
   ```

7. **Check service logs anytime:**
   ```bash
   journalctl -u busy-laundry.service -f
   ```

---

## ⚙️ Customization Options (`.env`)

| Variable | Default | Description |
|---|---|---|
| `BUSY_BAR_IP` | `192.168.1.100` | Local network IP address of your BUSY Bar |
| `LAUNDRY_DEVICE_ID` | *(empty)* | Sinric Pro device ID for unified laundry switch |
| `WASHER_DEVICE_ID` | *(empty)* | Sinric Pro device ID for washer switch |
| `DRYER_DEVICE_ID` | *(empty)* | Sinric Pro device ID for dryer switch |
| `LAUNDRY_ALERT_TEXT` | `Laundry done` | Notification text displayed on matrix |
| `ALERT_SOUND` | `event` | Sound played on BUSY Bar (`event`, `reminder`, `volume`, or empty) |
| `ALERT_TIMEOUT_SECONDS` | `1800` (30 mins) | Time until message automatically disappears |

---

## 💡 Pro-Tips
- **Turn Off via Voice:** You can say *"Hey Google, turn off washer alert"* or *"turn off laundry"* and the bridge will immediately clear the BUSY Bar screen!
- **Zero Port Forwarding:** Sinric Pro uses outgoing WebSockets, so you do **not** need to open any ports or mess with firewall rules on your home router.
