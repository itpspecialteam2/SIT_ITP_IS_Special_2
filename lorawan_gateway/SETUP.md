# LoRaWAN Gateway - Setup Instructions
**Singapore Institute of Technology - ITP Project IS1 Team IS Special 2**

---

## Prerequisites

Before starting, ensure the following are in place:

- Raspberry Pi is running with HAProxy configured and listening on port 9993
- Classical CA and gateway client certificates have been generated on the Pi
- The Pi's local IP address is known (default: `192.168.0.105`)
- You have admin access to the UG56 web GUI and SSH credentials
- The OQS Mosquitto broker is running on the Pi on port 8883

---

## Part 1 - Primary Route Setup (Built-in MQTT Publisher)

This configures the gateway's built-in firmware MQTT publisher to connect to HAProxy on the Pi over TLS 1.3.

### Step 1 - Generate Gateway Client Certificate on the Pi

On the Raspberry Pi, run the following commands to generate a client certificate for the gateway:

```bash
cd /home/admin/Desktop/Project/mosquitto/certs

openssl genrsa -out gateway.key 2048

openssl req -new -key gateway.key -out gateway.csr \
  -subj "/CN=lorawan-gateway/O=SIT-ProjectIS1/C=SG"

openssl x509 -req -days 3650 -in gateway.csr \
  -CA ca.crt -CAkey ca.key \
  -CAserial ca.srl -out gateway.crt

# Verify
openssl verify -CAfile ca.crt gateway.crt
```

### Step 2 - Configure the Gateway Web GUI

Access the gateway web UI from the Pi's browser at `http://<gateway_ip>`.

1. Log in with admin credentials
2. Navigate to **Network Server → Application**
3. Find the MQTT uplink configuration for the HomeAssistant application
4. Set the following:
   - **Broker Address:** `192.168.0.105`
   - **Port:** `9993`
   - **TLS:** Enabled
   - **Self-signed certificates:** Enabled
5. Upload the following files from `/home/admin/Desktop/Project/mosquitto/certs/`:
   - **CA Certificate:** `ca.crt`
   - **Client Certificate:** `gateway.crt`
   - **Client Key:** `gateway.key`
6. Save and apply

### Step 3 - Verify Primary Route

On the Pi, subscribe to the uplink topic and confirm sensor data is flowing:

```bash
mosquitto_sub -h localhost -p 8883 \
  --cafile /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt \
  --cert /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt \
  --key /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.key \
  --insecure \
  -t "milesight/uplink/#" -v
```

You should see readable JSON sensor payloads arriving within a few minutes. Also check the OQS Mosquitto logs to confirm the connection:

```bash
sudo journalctl -u mosquitto-oqs --no-pager | tail -20
```

Look for a line containing `New client connected` from the gateway IP address.

---

## Part 2 - Alternative Route Setup (AES-256 Python Bridge)

This sets up `encrypt.py` on the gateway Python SDK and `decrypt.py` on the Pi for the AES-256 alternative uplink route.

### Overview

```
Gateway internal broker (:18883)
    ↓ encrypt.py subscribes and encrypts with AES-256-CBC
HAProxy on Pi (:9993) over TLS 1.2
    ↓ HAProxy upgrades to PQ TLS 1.3
Mosquitto broker (:8883) - stores on milesight/encrypted/<devEUI>
    ↓ decrypt.py subscribes and decrypts
milesight/uplink/<devEUI> - consumed by Home Assistant
```

---

### Step 1 - Create Persistent Certificate Directory on Gateway

SSH into the gateway and run the following via the Python SDK:

```
en
config t
python
debug setup_certs.py
```

Use the `setup_certs.py` script from the `scripts/` directory. This creates `/home/pyuser/certs/` for persistent certificate storage.

> **Why:** `/tmp` is cleared on every reboot. All certificates must be stored in `/home/pyuser/certs/` to persist across reboots.

---

### Step 2 - Generate Internal Client Certificate on Gateway

Run `generate_internal_cert.py` via the Python SDK debug console:

```
debug generate_internal_cert.py
```

This script copies the internal CA from `/etc/ssl/certs/` to `/home/pyuser/certs/` and generates a client certificate signed by the internal CA, stored at `/home/pyuser/certs/client.crt` and `/home/pyuser/certs/client.key`.

> **Why:** The internal gateway broker on port 18883 requires mutual TLS. A client certificate signed by the internal CA is needed for `encrypt.py` to connect to it.

---

### Step 3 - Download Pi Certificates to Gateway

On the Pi, start a temporary HTTP server:

```bash
cd /home/admin/Desktop/Project/mosquitto/certs
python3 -m http.server 9999
```

On the gateway, run `download_pi_certs.py` via the Python SDK debug console:

```
debug download_pi_certs.py
```

This downloads `ca.crt`, `gateway.crt`, and `gateway.key` from the Pi to `/home/pyuser/certs/` on the gateway.

After the download completes, stop the HTTP server on the Pi with `Ctrl+C`.

---

### Step 4 - Verify Certificates on Gateway

Run `verify_certs.py` via the Python SDK debug console:

```
debug verify_certs.py
```

All six files should show as `EXISTS`:

```
/home/pyuser/certs/pi-ca.crt       EXISTS
/home/pyuser/certs/pi-gateway.crt  EXISTS
/home/pyuser/certs/pi-gateway.key  EXISTS
/home/pyuser/certs/client.crt      EXISTS
/home/pyuser/certs/client.key      EXISTS
/home/pyuser/certs/ca-mqtt.crt     EXISTS
```

---

### Step 5 - Upload and Run encrypt.py on Gateway

Upload `encrypt.py` to the gateway via the Python SDK:

```
edit-script encrypt.py
```

Paste the contents of `encrypt.py` from the `scripts/` directory.

Run it:

```
debug encrypt.py
```

Expected output:

```
Starting AES-256 Encryption Bridge...
Internal broker : 127.0.0.1:18883
HAProxy on Pi   : 192.168.0.105:9993
AES key length  : 32 bytes (256 bits)
[PUBLISHER] Connecting to HAProxy on Pi...
[PUBLISHER] Connected to HAProxy on Pi
[SUBSCRIBER] Connecting to internal broker...
[SUBSCRIBER] Connected to internal gateway broker
[SUBSCRIBER] Subscribed to: application/2/device/+/rx
Running...
[BRIDGE] application/2/device/<devEUI>/rx -> milesight/encrypted/<devEUI>
[BRIDGE] Original length: 574 Encrypted length: 792
```

---

### Step 6 - Set Up decrypt.py on the Pi

#### 6a - Generate PQC Client Certificate for decrypt.py

On the Pi, generate a client certificate signed by the OQS Mosquitto's ML-DSA-65 CA:

```bash
cd /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65

openssl genpkey -algorithm mldsa65 -out decrypt-bridge.key

openssl req -new -key decrypt-bridge.key -out decrypt-bridge.csr \
  -subj "/CN=decrypt-bridge/O=SIT-ProjectIS1/C=SG"

openssl x509 -req -days 3650 \
  -in decrypt-bridge.csr \
  -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out decrypt-bridge.crt

openssl verify -CAfile ca.crt decrypt-bridge.crt
```

#### 6b - Run decrypt.py

Copy `decrypt.py` to the Pi and run it:

```bash
python3 /home/admin/Desktop/Project/decrypt.py
```

Expected output:

```
============================================================
 AES-256 Decryption Bridge
 SIT IoT-PQC Project
============================================================
 Broker     : localhost:8883
 Subscribe  : milesight/encrypted/#
 Republish  : milesight/uplink/<devEUI>
 AES key    : 32 bytes (256 bits)
 Output fmt : sensor object only (matches primary firmware)
============================================================
[BRIDGE] Starting - press Ctrl+C to stop
[BRIDGE] Connected to Mosquitto broker
[BRIDGE] Subscribed to: milesight/encrypted/#
[BRIDGE] Decrypted milesight/encrypted/<devEUI> -> milesight/uplink/<devEUI>
[BRIDGE] Payload: {"battery":80,"co2":366,"humidity":56.5,"temperature":24}
```

---

### Step 7 - Verify Alternative Route End to End

On the Pi, open two terminals simultaneously:

**Terminal 1 - watch encrypted payloads:**
```bash
mosquitto_sub -h localhost -p 8883 \
  --cafile /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt \
  --cert /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt \
  --key /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.key \
  --insecure \
  -t "milesight/encrypted/#" -v
```

**Terminal 2 - watch decrypted output:**
```bash
mosquitto_sub -h localhost -p 8883 \
  --cafile /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt \
  --cert /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt \
  --key /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.key \
  --insecure \
  -t "milesight/uplink/#" -v
```

Terminal 1 should show base64 ciphertext. Terminal 2 should show readable JSON sensor objects. Both updating confirms the full pipeline is working.

> **Note:** If both the primary route and the alternative route are running simultaneously, you will see two outputs per sensor transmission on `milesight/uplink/#` - one from each route.

---

## Important Notes

- **The AES_KEY must match on both ends.** If you change the key in `encrypt.py`, update `decrypt.py` on the Pi as well.
- **Certificates in `/home/pyuser/certs/` persist across reboots.** If you regenerate certs on the Pi, you must re-download them to the gateway using Step 3.
- **Kill existing script instances before starting a new one.** Duplicate client IDs cause connection loops. See `TROUBLESHOOTING.md` for how to detect and kill existing instances.
