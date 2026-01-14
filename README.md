# Taylor Grill Local Integration

A fully local Home Assistant integration for **Taylor Grill** Smoker Controllers (and potentially other generic pellet smoker controllers) using the proprietary `FA 09...` binary protocol over MQTT.

**Features:**
* 🚀 **100% Local:** Bypasses the cloud entirely.
* 🌡️ **Full Control:** Set Target Temperature (up to 500°F in 5° increments).
* 🔌 **Power Control:** Turn the smoker On or Off.
* 📊 **Sensors:** Reads Internal Probe + 3 External Probes.
* 🚩 **Binary Sensors:** Reads the error flags that can be sent by the controller and will update the binary sensor in HomeAssistant.
   * 📝 **Note**: Not all sensors may be used by your model. This integration supports the following error sensors:
      * Fan Error
      * Auger Motor Error
      * Ignition Error
      * No Pellets (Hopper Empty)
      * High Temp Alert
      * System Errors 1/2/3
* 🛠️ **Config Flow:** Easy setup via Home Assistant UI.

---

## ⚠️ Important Warnings

**1. This Will Break the Official App**
This integration requires "hijacking" the smoker's connection to the cloud. Once configured, your smoker will talk to Home Assistant *instead* of the manufacturer's server. The official mobile app will be unable to connect to the smoker/grill over WiFi. Bluetooth should still work.

**2. Disclaimer**
This software is BETA software. It is provided "as is", without warranty of any kind, express or implied. Use it at your own risk. The authors take no responsibility for any damage to your hardware, voided warranties, or ruined briskets.

**3. Compatibility**
This integration has been tested specifically with [this Replacement Thermostat Controller](https://www.amazon.com/Replacement-Thermostat-Controller-Bluetooth-Temperature/dp/B0FVK8N5MS). While it *should* work with other "Taylor Grill" branded controllers that use the same ESP32 architecture and port 1883/18041, it is not guaranteed.
   * As long as it uses the "[Smarter Grill](https://play.google.com/store/apps/details?id=com.zhibaowang.jiuze.example.xxx.grill)" app, it should work with this.
   * It is possible that this will work with devices that use [similar apps from the same developer](https://play.google.com/store/apps/developer?id=My+grill). But this has not been confirmed. If you have a device that uses one of these similar apps, and this integration does not work for you, open an issue, and let me know. I'll try to add support if possible.

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
5.  Enter your temperature unit preference.

---

## Finding Your Device ID
The Device ID is required during setup. It will typically start with `GRILLS`. This is also found in the App and will show as the name when connecting via Bluetooth. It is also sometimes printed on a sticker on the controller itself.

**Check MQTT Logs:**
If you have successfully set up the Network Hijack (Prerequisite #1), watch your Mosquitto logs when you plug in the smoker. You will see a client connect with the ID you need:

```
New client connected from 192.168.1.50 as GRILLS12345678...
```
Enter GRILLS12345678 (or whatever your log shows) into the setup dialog.

---

## 🛣️ Roadmap:
**Bluetooth:** Expand support to communicate over bluetooth rather than a hijacked MQTT connection.

**App Compatibility:** See if there is a way to keep the app working.

**Additional/Advanced Features:**
   * **PID:** Explore if it is possible to read/adjust PID (Proportional, Integral, Derivative) values.
   * **Timer/Recipe:** Explore if its possible to setup a "Recipe" of sorts. Hold the themp at XXX Degrees for Y Hours, then change temp to XXX Degrees for Y Hours.

**Suggestions:** Open an issue and I will let you know if its feasible or not.

---

## Troubleshooting

### 1. Enable Debug Logging 
If you are having issues (weird temperatures, commands not working, etc...), the best way to see what is happening is to enable debug logging. This will print the raw hex data coming from the smoker to your Home Assistant logs.

1.  Go to **Settings** > **Devices & Services**.
2.  Click on the **Taylor Grill** integration.
3.  On the left side, click **Enable Debug Logging** (Newer HA releases have this in the 3 dot menu in the upper right).
4.  Interact with the device (turn it on, change temp, etc.).
5.  When finished, click **Disable Debug Logging**.
6.  The log file will show lines starting with `RAW MQTT PACKET`.

### 2. Smoker shows "Unavailable" or Won't Connect
* **Check Mosquitto Logs:** Does it show "New client connected"?
* **Check for "Triangle Routing" (NAT Users):** If you see the smoker connect and immediately disconnect (or see `RST` flags in tcpdump), you likely missed **Step 2 (Masquerade/SNAT)** in the Network Setup.
    * *Symptom:* HA replies to the smoker, but the smoker rejects the packet because it came from the wrong IP.
    * *Fix:* Ensure your Router is configured to **Masquerade** traffic destined for Port 1883.

### 3. Temperature readings are wrong or missing?
* **Internal Probe:** If the Internal Probe reads "Unknown" or weird values, enable Debug Logging and check the raw hex.
     * A good tip is to enable debug logging and then hold the internal probe in your hand or pinch between 2 fingers to warm it up. Do this for a couple of minutes to see if the temperature updates.
* **External Probes:** The smoker only reports external probe temps when they are plugged in. If unplugged, they will show "Unknown".
    * The integration ignores values where the "Hundreds" digit is > 5 (e.g., 960°F) as these are usually error codes from the hardware.
* **Packet Filtering:** The smoker sends two types of messages: "Status" (On/Off) and "Sensors" (Temps). The integration filters these automatically, but a weak Wi-Fi signal can cause packet loss.

### 4. Can't control the grill?
* **Check Power State:** Ensure the "Power" switch in Home Assistant matches the physical state of the grill.
* **Verify Topics:** Enable Debug Logging and look for `Sending Set Temp...`. If you see the log but the grill doesn't beep, the grill might not be subscribed to the `/app2dev` command topic (check your Device ID configuration).

---
## Contributing
Pull requests are welcomed! If you find a bug or want to add support for other models, please feel free to contribute.
