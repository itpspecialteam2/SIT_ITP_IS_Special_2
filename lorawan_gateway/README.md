# LoRaWAN Gateway - Handover Documentation
**Singapore Institute of Technology - ITP Project IS1 Team IS Special 2**

---

## Overview

This directory covers everything related to the Milesight UG56 LoRaWAN gateway in the IoT-PQC project. The gateway receives sensor data from four LoRaWAN devices over radio and forwards decoded MQTT messages to the Raspberry Pi.

Two uplink routes have been implemented:

| Route | Description | TLS | PQC |
|---|---|---|---|
| Primary | Built-in firmware MQTT publisher → HAProxy on Pi | TLS 1.3 | PQ key exchange via HAProxy |
| Alternative | `encrypt.py` Python SDK script → HAProxy on Pi | TLS 1.2 | AES-256-CBC payload encryption + PQ key exchange via HAProxy |

The primary route is the default and handles both uplink (sensor data) and downlink (HA commands to sensors). The alternative route handles uplink only and provides an additional layer of quantum-safe payload encryption using a pre-shared AES-256-CBC key.

---

## Hardware

- **Device:** Milesight UG56 LoRaWAN Gateway
- **Firmware version:** 56.0.0.3-r1
- **Architecture:** aarch64 (64-bit ARM)
- **Kernel:** 4.4.143
- **Storage:** eMMC (persistent), tmpfs `/tmp` (cleared on reboot)

---

## Sensors

| Device | Model | Protocol | Data |
|---|---|---|---|
| Environment Sensor | AM103 | LoRaWAN | Temperature, humidity, CO₂, battery |
| Smart Switch | WS558 | LoRaWAN | Switch states (8 channels) |
| Smart Button | WS101 | LoRaWAN | Battery, button events |
| Leak Detector | WS303 | LoRaWAN | Leak status, battery |

Sensor data is received over LoRa radio using AES-128 MAC layer encryption as defined by the LoRaWAN specification. The embedded network server on the gateway decrypts and decodes the payloads before forwarding them as MQTT messages.

---

## Gateway Access

| Method | Details |
|---|---|
| Web GUI | `http://<gateway_ip>` - admin credentials required |
| SSH | Port 22, restricted Cisco-style CLI only |
| Python SDK (upload) | Web GUI → App → Python → SDK Upload |
| Python SDK (debug/run) | SSH into CLI, then use Python commands below |

> **Important:** SSH access drops into a restricted Cisco-style CLI shell, not a Linux bash shell. Standard Linux commands (`ls`, `python3`, `cat`) are not available from SSH.

> **Important:** SCP does not work via SSH because the gateway's SSH shell outputs text on connection, which breaks SCP's protocol. File transfers must be done using `wget` from within the Python SDK, pulling files from a temporary HTTP server on the Pi.

### Accessing the Python SDK via CLI

To run or debug Python scripts, SSH into the gateway and follow these steps:

```
# Enter privileged mode
en

# Enter configuration mode
config t

# Enter Python context
python

# Run a script
debug <script.py>

# Edit a script directly in the CLI
edit-script <script.py>

# See all available commands in current context
?
```

Scripts can also be uploaded via the Web GUI under **App → Python → SDK Upload**, but debugging and execution must be done through the CLI as shown above.

### Uploading Scripts

1. SSH into the gateway
2. Enter privileged mode: `en`
3. Enter config mode: `config t`
4. Enter Python context: `python`
5. Create or edit a script: `edit-script <script.py>`
6. Run the script: `debug <script.py>`

---

## Python SDK Environment

The gateway Python SDK environment has the following constraints that are important to understand before attempting any modifications:

| Property | Value |
|---|---|
| Python version | 2.7.13 |
| OpenSSL version | 1.0.2k (January 2017) |
| Max TLS version | TLS 1.2 (TLS 1.3 was finalised August 2018, after this OpenSSL) |
| PQC support | None |
| Available crypto | `paho-mqtt`, `ctypes`, `hashlib`, `ssl`, `hmac` |
| Persistent storage | `/home/pyuser/` (eMMC), `/home/admin/` (eMMC) |
| Temporary storage | `/tmp` (cleared on reboot) |

---

## PQC Investigation Findings

The following approaches were investigated to determine whether PQC could be implemented natively on the gateway. Findings are shown below.

| Approach | Finding | Conclusion |
|---|---|---|
| Web GUI TLS settings | Only CA/cert upload fields, no cipher suite selection | Classical TLS only |
| SSH CLI | Cisco-style restricted shell, no Linux access | Cannot run custom commands |
| Python SDK crypto | Python 2.7 + OpenSSL 1.0.2k, no PQC libraries available | No PQC possible from Python |
| Wireshark ClientHello | Only classical groups advertised: `x25519`, `secp256r1`, `secp384r1`, `secp521r1` | Firmware TLS stack has no PQC groups |
| Firmware release notes | Reviewed all versions up to 56.0.0.9-r1, no PQC additions documented | Firmware upgrade will not help |
| Architecture compatibility | aarch64, kernel 4.4.143 - glibc version mismatch prevents bundling newer Python runtime | Cannot bundle newer OpenSSL |

**Conclusion:** Native PQC on this gateway is not achievable at any accessible layer. The proxy architecture (HAProxy on the Pi) is the correct solution for upgrading the security of the gateway's MQTT connection to PQ TLS 1.3.

---

## Internal Broker

The gateway runs an internal Mosquitto broker used by the embedded network server to publish decoded sensor data. Key details:

| Property | Value |
|---|---|
| Port 1883 | Plaintext MQTT, requires username/password authentication |
| Port 18883 | MQTT over TLS, requires client certificate |
| Internal CA | `/etc/ssl/certs/ca-mqtt.crt` |
| Internal CA key | `/etc/ssl/certs/ca-mqtt.key` |
| Internal broker config | `/etc/mosquitto/mosquitto.conf` |
| Sensor data topic | `application/2/device/<devEUI>/rx` |

The Python bridge script (`encrypt.py`) connects to port 18883 using a client certificate generated from the internal CA. See `SETUP.md` for cert generation steps.

---

## Directory Structure

```
lorawan_gateway/
├── README.md                      - this file
├── SETUP.md                       - step by step setup instructions
├── TROUBLESHOOTING.md             - common issues and fixes
└── scripts/
    ├── setup_certs.py             - run first, creates /home/pyuser/certs/
    ├── generate_internal_cert.py  - generates client cert for internal broker
    ├── download_pi_certs.py       - downloads Pi certs to gateway via wget
    ├── verify_certs.py            - verifies all required cert files are present
    ├── encrypt.py                 - AES-256 encryption bridge (runs on gateway)
    └── decrypt.py                 - AES-256 decryption bridge (runs on Pi)
```

---

## Related Components

| Component | Location in repo |
|---|---|
| Decryption bridge | `pi/decrypt/` |
| HAProxy config (Pi) | `pi/haproxy/` |
| Mosquitto OQS broker | `pi/mosquitto-oqs/` |
| Classical CA and certs | `pi/certs/` |

---

## Key Notes for Next Team

1. **`/tmp` is cleared on reboot.** All certificate files must be stored in `/home/pyuser/certs/`. Do not store anything important in `/tmp`.

2. **The gateway has two separate TLS stacks.** The built-in firmware publisher uses a modern TLS stack (TLS 1.3 capable). The Python SDK uses OpenSSL 1.0.2k (TLS 1.2 maximum). These are completely independent.

3. **Duplicate client IDs will cause connection loops.** If `encrypt.py` is already running (e.g. from a previous session), starting it again will cause both instances to kick each other off the broker repeatedly. Kill existing instances before starting a new one.

4. **The alternative route is uplink only.** Downlink commands from Home Assistant to sensors only work through the primary firmware route. The AES-256 bridge does not handle downlink.

5. **Pre-shared key must match on both ends.** The `AES_KEY` in `encrypt.py` on the gateway must exactly match the `AES_KEY` in `decrypt.py` on the Pi. If you change one, change both.
