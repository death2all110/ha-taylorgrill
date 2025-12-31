# Taylor Grill Integration

A local Home Assistant integration for Taylor Grill Smoker Controllers (and potentially other generic pellet smoker controllers) using the proprietary `FA 09...` binary protocol over MQTT.

**Features:**
* 100% Local (Cloud Bypassed)
* Supports On/Off/Shutdown
* Sets Target Temperature
* Reads Current Temperature (Probe 1) via Sensor Hex Parsing

## Installation
1. Install via HACS by adding this repository as a "Custom Repository".
2. Go to Settings > Devices > Add Integration.
3. Search for "Taylor Grill".
4. Enter your Device ID (e.g., `GRILLSXXXXXXXX`).

## Requirements
* An MQTT Broker (Mosquitto) running and connected to Home Assistant.
* The Smoker must be redirected to your MQTT Broker (via DNS Hijack or Router NAT).