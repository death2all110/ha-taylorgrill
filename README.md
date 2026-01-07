# Taylor Grill Local Integration

A fully local Home Assistant integration for **Taylor Grill** Smoker Controllers (and potentially other generic pellet smoker controllers) using the proprietary `FA 09...` binary protocol over MQTT.

**Features:**
* 🚀 **100% Local:** Bypasses the cloud entirely.
* 🌡️ **Full Control:** Set Target Temperature (up to 500°F in 5° increments).
* 🔌 **Power Control:** Turn the smoker On or Off (Shutdown sequence).
* 📊 **Sensors:** Reads Internal Probe + 3 External Probes.
* 🛠️ **Config Flow:** Easy setup via Home Assistant UI.

---

## ⚠️ Important Warnings

**1. This Will Break the Official App**
This integration requires "hijacking" the smoker's connection to the cloud. Once configured, your smoker will talk to Home Assistant *instead* of the manufacturer's server. The official mobile app will likely show the device as "Offline" and will no longer function.

**2. Disclaimer**
This software is provided "as is", without warranty of any kind, express or implied. Use it at your own risk. The authors take no responsibility for any damage to your hardware, voided warranties, or ruined briskets.

**3. Compatibility**
This integration has been tested specifically with [this Replacement Thermostat Controller](https://www.amazon.com/Replacement-Thermostat-Controller-Bluetooth-Temperature/dp/B0FVK8N5MS). While it *should* work with other "Taylor Grill" branded controllers that use the same Tuya/ESP32 architecture and port 1883/18041, it is not guaranteed.

---

## ⚠️ Critical Prerequisites
**Before installing this integration, you must configure your network to "trick" the smoker into talking to Home Assistant instead of the cloud.**

### 1. Network Hijack (The "Man-in-the-Middle")
The smoker is hardcoded to connect to `iot.taylorgrill.com`. You must redirect this traffic to your Home Assistant IP address. You can do this in **one** of two ways:

* **Option A: DNS Override (Easiest)**
    * In your DNS Server (AdGuard Home, Pi-hole, OPNsense, or Router), create a **DNS Rewrite** or **Host Override**:
        * **Domain:** `iot.taylorgrill.com`
        * **IP:** `[Your Home Assistant IP]`
    
* **Option B: NAT Redirection (Best/Most Robust)**
    * In your Router/Firewall (e.g., EdgeRouter, OPNsense, pfSense, UniFi), you must perform **TWO** steps to hijack port 1883.
    
    * **Step 1: Destination NAT (DNAT)**
        * **Goal:** Catch the traffic leaving the smoker.
        * **Interface:** LAN (or the network your smoker is on).
        * **Source IP:** `[Smoker IP]`
        * **Destination Port:** `1883` (MQTT)
        * **Action/Translation:** Redirect to `[Your Home Assistant IP]` at Port `1883`.

    * **Step 2: Source NAT / Masquerade (Crucial!)**
        * **Goal:** Trick Home Assistant into replying to the *Router* instead of the Smoker.
        * **Interface:** LAN (or the network your smoker is on).
        * **Rule Type:** Source NAT (SNAT) or "Outbound NAT".
        * **Source IP:** `[Smoker IP]`
        * **Destination IP:** `[Your Home Assistant IP]`
        * **Destination Port:** `1883`
        * **Action/Translation:** **Masquerade** (sometimes called "NAT to Interface Address").
        
        * **Why?** This ensures the return traffic goes `Home Assistant -> Router -> Smoker`. Without it, HA tries to reply directly to the smoker (`HA -> Smoker`), which the smoker rejects because it's expecting a reply from the Cloud IP.

### 2. MQTT Broker Credentials
The smoker will attempt to log in with a hardcoded username and password. You must add this user to your Mosquitto Broker in Home Assistant.

* **Username:** `Taylor`
* **Password:** `YKC6WLIFUZaBaMQU`
    * *(This password is hardcoded in the firmware)*

**Alternative:** Set `anonymous: true` in your Mosquitto configuration to allow it to connect without matching credentials.

---

## Installation

### Step 1: Install via HACS
1.  Open HACS in Home Assistant.
2.  Go to **Integrations** > **Top Right Menu (⋮)** > **Custom repositories**.
3.  Paste this repository URL.
4.  Category: **Integration**.
5.  Click **Add**, then click **Download**.
6.  **Restart Home Assistant**.

### Step 2: Add Integration
1.  Go to **Settings** > **Devices & Services**.
2.  Click **+ Add Integration**.
3.  Search for **"Taylor Grill"**.
4.  Enter your **Device ID** (see below).

---

## Finding Your Device ID
The Device ID is required during setup. It will typically start with `GRILLS`.

**Check MQTT Logs:**
If you have successfully set up the Network Hijack (Prerequisite #1), watch your Mosquitto logs when you plug in the smoker. You will see a client connect with the ID you need:

```
New client connected from 192.168.1.50 as GRILLS12345678...
```
Enter GRILLS12345678 (or whatever your log shows) into the setup dialog.

---

## Troubleshooting

**Smoker shows "Unavailable"?**
* Check your Mosquitto logs. Is the device connecting?
* If not, your **DNS/NAT Redirection** is not working. The smoker must think Home Assistant is `iot.taylorgrill.com`.

**Temperature readings are weird?**
* The smoker reports different data packets for "Status" vs "Sensors". This integration automatically filters them, but ensure you have a stable Wi-Fi connection.

**Can't control the grill?**
* Ensure the "Power" switch in Home Assistant is matching the physical state. The integration relies on MQTT "Command" topics (`/app2dev`) which require the broker to be fully operational.

---
## Contributing
Pull requests are welcomed! If you find a bug or want to add support for other models, please feel free to contribute.