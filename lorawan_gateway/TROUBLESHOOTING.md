# LoRaWAN Gateway - Troubleshooting
**Singapore Institute of Technology - ITP Project IS1 Team IS Special 2**

---

## Primary Route Issues

### Sensor data not appearing on `milesight/uplink/#`

**Check 1 - Is the gateway MQTT connection active?**

Log into the gateway web GUI and navigate to **Network Server → Application**. Check the MQTT connection status. If it shows disconnected, verify:
- HAProxy is running on the Pi on port 9993
- The broker address and port are set correctly (`192.168.0.105:9993`)
- The certificate files uploaded are not expired

**Check 2 - Check OQS Mosquitto logs**

```bash
sudo journalctl -u mosquitto-oqs --no-pager | tail -30
```

Look for:
- `New client connected from 192.168.0.102` - gateway connected successfully
- `unknown ca` - certificate CA mismatch, re-upload the correct `ca.crt` to the gateway web GUI
- `tlsv1 alert unknown ca` - same issue, CA cert mismatch

**Check 3 - Is OQS Mosquitto running?**

```bash
sudo systemctl status mosquitto-oqs
ps aux | grep mosquitto
sudo ss -tlnp | grep 8883
```

If not running, restart it:

```bash
sudo systemctl restart mosquitto-oqs
```

**Check 4 - Is HAProxy running on port 9993?**

```bash
sudo ss -tlnp | grep 9993
```

If nothing is listening on 9993, HAProxy is not running. Restart it:

```bash
sudo systemctl restart haproxy
```

---

### Gateway connects but immediately disconnects

This typically means TLS handshake succeeded but MQTT authentication failed.

Check the Mosquitto logs for the specific error:

```bash
sudo journalctl -u mosquitto-oqs --no-pager | grep -E "connected|disconnected|error" | tail -20
```

Common causes:
- **`Protocol error`** - TLS version or cipher suite mismatch between gateway and HAProxy
- **`bad user name or password`** - Mosquitto requires credentials but none provided. Check `allow_anonymous` setting in `/opt/mosquitto-oqs/config/mosquitto.conf`
- **`certificate verify failed`** - Client cert signed by wrong CA

---

## Alternative Route Issues (encrypt.py / decrypt.py)

### encrypt.py connection error on startup

**`[PUBLISHER] Connection error: SSLError TLSV1_ALERT_PROTOCOL_VERSION`**

The Pi broker or HAProxy is rejecting TLS 1.2. The gateway Python SDK is limited to TLS 1.2 due to OpenSSL 1.0.2k. Check that HAProxy's frontend on port 9993 accepts TLS 1.2:

```bash
openssl s_client -connect localhost:9993 -tls1_2 \
  -CAfile /home/admin/Desktop/Project/mosquitto/certs/ca.crt 2>&1 | head -5
```

Should show `CONNECTED` and `Protocol: TLSv1.2`. If it fails, check the HAProxy config - the `bind` directive on port 9993 should not have `ssl-min-ver TLSv1.3`.

---

**`[PUBLISHER] Connection error: No such file or directory`**

Certificate files are missing from `/home/pyuser/certs/`. This happens after a reboot because certs were previously stored in `/tmp`.

Re-run the cert setup on the gateway:

```
debug generate_internal_cert.py
debug download_pi_certs.py
debug verify_certs.py
```

---

**`[PUBLISHER] Connection error: hostname verification failed`**

The HAProxy server certificate CN does not match the IP address being connected to. This is expected - add `tls_insecure_set(True)` in `encrypt.py` if not already present. This skips hostname verification while keeping all other TLS security intact.

---

### encrypt.py connects then immediately disconnects in a loop

**Symptom:**
```
[PUBLISHER] Connected to HAProxy on Pi
[PUBLISHER] Disconnected from Pi, rc: 1
[SUBSCRIBER] Connected to internal gateway broker
[SUBSCRIBER] Disconnected from internal broker, rc: 1
```

**Cause:** Another instance of `encrypt.py` is already running with the same client IDs (`gateway-aes-publisher` and `gateway-aes-subscriber`). MQTT brokers only allow one connection per client ID - the two instances kick each other off repeatedly.

**Fix:** Check for existing running processes via the gateway Python SDK:

```python
import subprocess
r = subprocess.Popen(['ps', 'aux'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = r.communicate()
print(out)
```

Kill all existing Python processes:

```python
import subprocess
r = subprocess.Popen(['killall', 'python'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = r.communicate()
print("Done")
```

Then restart `encrypt.py`.

---

### encrypt.py running but no encrypted messages arriving on Pi

**Check 1 - Is decrypt.py running on the Pi?**

```bash
ps aux | grep decrypt
```

If not running, start it:

```bash
python3 /home/admin/Desktop/Project/decrypt.py
```

**Check 2 - Are encrypted messages arriving at the broker?**

```bash
mosquitto_sub -h localhost -p 8883 \
  --cafile /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt \
  --cert /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt \
  --key /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.key \
  --insecure \
  -t "milesight/encrypted/#" -v
```

If nothing appears, the issue is on the gateway side - check `encrypt.py` output for errors.

If base64 ciphertext appears but `milesight/uplink/#` is empty, the issue is with `decrypt.py` - check its output for errors.

**Check 3 - Is the internal broker publishing sensor data?**

Run this check script on the gateway to confirm sensor data is flowing from the internal broker:

```
debug verify_certs.py
```

Then run a quick subscription test via Python SDK to confirm the internal broker is publishing:

```python
import paho.mqtt.client as mqtt
import ssl
import time

def on_connect(c, u, f, rc):
    print("Internal broker rc:", rc)
    if rc == 0:
        c.subscribe("application/2/device/+/rx")

def on_message(c, u, msg):
    print("Message received:", msg.topic, msg.payload[:50])

c = mqtt.Client(client_id="test-sub-123")
c.on_connect = on_connect
c.on_message = on_message
c.tls_set(
    ca_certs="/home/pyuser/certs/ca-mqtt.crt",
    certfile="/home/pyuser/certs/client.crt",
    keyfile="/home/pyuser/certs/client.key",
    tls_version=ssl.PROTOCOL_TLSv1_2
)
c.tls_insecure_set(True)
c.connect("127.0.0.1", 18883, 60)
c.loop_start()
time.sleep(30)
c.loop_stop()
```

If messages appear, the internal broker is working and the issue is in `encrypt.py`. If nothing appears after 30 seconds, the internal broker is not publishing - check the gateway's embedded network server status in the web GUI.

---

### decrypt.py fails with certificate verify failed

**`SSL: CERTIFICATE_VERIFY_FAILED - self-signed certificate in certificate chain`**

`decrypt.py` is using the wrong CA. It must use the ML-DSA-65 CA that the OQS Mosquitto trusts, not the classical CA.

Verify the CA path in `decrypt.py`:

```python
CA_CERT = "/home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt"
```

Also verify the client cert was signed by that same CA:

```bash
openssl verify \
  -CAfile /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt \
  /home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt
```

Should return `decrypt-bridge.crt: OK`. If it fails, regenerate the cert following Step 6a in `SETUP.md`.

---

### decrypt.py fails with hostname mismatch

**`Hostname mismatch, certificate is not valid for 'localhost'`**

The OQS Mosquitto broker certificate does not have `localhost` as a SAN. Ensure `tls_insecure_set(True)` is present in `decrypt.py` after the `tls_set()` call.

---

### Decrypted values not updating in Home Assistant

**Symptom:** `decrypt.py` is running and publishing to `milesight/uplink/#` but Home Assistant sensor values are not changing.

**Check 1 - Verify the topic format matches what HA expects**

Subscribe to `milesight/uplink/#` and check the payload format:

```bash
mosquitto_sub ... -t "milesight/uplink/#" -v
```

The output should be a plain sensor object: `{"battery":80,"co2":366,"humidity":56.5,"temperature":24}`. If it shows the full application JSON including `applicationID`, `rxInfo` etc., the `decrypt.py` object extraction is not working correctly - check the `on_message` function for the `full_payload.get('object', full_payload)` line.

**Check 2 - Is Home Assistant subscribed to the correct topic?**

In Home Assistant, go to **Developer Tools → States** and check the last updated time of your sensor entities. If they are stale, HA may not be subscribed to `milesight/uplink/#`. Check the MQTT integration configuration in HA.

---

## Certificate Issues

### Certificates missing after reboot

All files in `/tmp` are cleared on reboot. If you stored certificates in `/tmp` previously, they will be gone.

Re-run on the gateway:
```
debug generate_internal_cert.py
debug download_pi_certs.py
debug verify_certs.py
```

Always store certificates in `/home/pyuser/certs/` - this is persistent eMMC storage.

---

### Certificate signing fails with serial file error

**`error: fopen('/etc/ssl/certs/ca-mqtt.srl','w') Permission denied`**

The signing process tried to write the serial file to `/etc/ssl/certs/` which is read-only. The internal CA files must be copied to a writable location before signing.

`generate_internal_cert.py` handles this automatically by copying the CA to `/home/pyuser/certs/` first. If you are running OpenSSL commands manually, ensure `-CA` and `-CAkey` point to files in `/home/pyuser/certs/`, not `/etc/ssl/certs/`.

---

### `openssl x509` produces an empty certificate file

This is caused by the serial file write error above. The signing command appears to succeed but produces an empty file. Verify the cert is valid after generation:

```python
import subprocess
r = subprocess.Popen(
    ['openssl', 'x509', '-in', '/home/pyuser/certs/client.crt', '-noout', '-subject'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print(out, err)
```

If it returns an error, re-run `generate_internal_cert.py`.

---

## General Checks

### Verify all cert files are present

```
debug verify_certs.py
```

### Check what ports are listening on the gateway

```python
import subprocess
r = subprocess.Popen(['netstat', '-tlnp'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = r.communicate()
print(out)
```

Expected ports: `1883`, `18883`, `80`, `443`, `22`, `9001`

### Check gateway architecture and kernel

```python
import subprocess
r = subprocess.Popen(['uname', '-a'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
out, err = r.communicate()
print(out)
```

Expected: `aarch64` architecture, kernel `4.4.143`

### Check Python and OpenSSL versions on gateway

```python
import sys
import ssl
print("Python:", sys.version)
print("OpenSSL:", ssl.OPENSSL_VERSION)
```

Expected: Python `2.7.13`, OpenSSL `1.0.2k`
