# Custom OQS Mosquitto Broker Setup Guide

This guide explains how to install, build, configure, and test a custom Mosquitto MQTT broker linked against a custom OQS/OpenSSL build.

The goal is to support:

```text
TLS 1.3
mTLS
ML-DSA certificates
X25519MLKEM768 hybrid key exchange
MQTT publish/subscribe testing
```

## Project Paths Used

```text
Custom OpenSSL:
  /opt/openssl-3.5

Custom Mosquitto install:
  /opt/mosquitto-oqs

Mosquitto config:
  /opt/mosquitto-oqs/config/mosquitto.conf

OpenSSL PQC config:
  /opt/mosquitto-oqs/config/openssl-pqc.cnf

Mosquitto cert folder:
  /opt/mosquitto-oqs/certs

Systemd service:
  /etc/systemd/system/mosquitto-oqs.service
```

---

# 1. Check OQS OpenSSL

Check the OpenSSL version:

```bash
/opt/openssl-3.5/bin/openssl version -a
```

Check that the OQS provider is available:

```bash
OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf \
/opt/openssl-3.5/bin/openssl list -providers
```

Expected providers:

```text
default
oqsprovider
```

---

# 2. Install Build Dependencies

```bash
sudo apt update

sudo apt install -y \
  build-essential \
  git \
  cmake \
  pkg-config \
  libcjson-dev \
  libsystemd-dev \
  libwrap0-dev \
  libreadline-dev \
  libedit-dev \
  libargon2-dev
```

Stop the default Mosquitto service if it exists:

```bash
sudo systemctl stop mosquitto 2>/dev/null || true
sudo systemctl disable mosquitto 2>/dev/null || true
```

---

# 3. Clone Mosquitto Source Code

```bash
mkdir -p ~/pqc-testbed/src
cd ~/pqc-testbed/src

git clone https://github.com/eclipse-mosquitto/mosquitto.git
cd mosquitto
```

Alternative clone URL:

```bash
git clone https://github.com/eclipse/mosquitto.git
cd mosquitto
```

---

# 4. Build Mosquitto Against Custom OpenSSL

Remove any old build folder:

```bash
rm -rf build
```

Configure with CMake:

```bash
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/mosquitto-oqs \
  -DCMAKE_PREFIX_PATH=/opt/openssl-3.5 \
  -DOPENSSL_ROOT_DIR=/opt/openssl-3.5 \
  -DOPENSSL_INCLUDE_DIR=/opt/openssl-3.5/include \
  -DOPENSSL_SSL_LIBRARY=/opt/openssl-3.5/lib/libssl.so \
  -DOPENSSL_CRYPTO_LIBRARY=/opt/openssl-3.5/lib/libcrypto.so \
  -DWITH_TLS=ON \
  -DWITH_TLS_PSK=ON \
  -DWITH_CJSON=ON \
  -DWITH_WEBSOCKETS=OFF \
  -DWITH_DOCS=OFF \
  -DWITH_TESTS=OFF
```

Build:

```bash
cmake --build build -j$(nproc)
```

Install:

```bash
sudo cmake --install build
```

---

# 5. Check OpenSSL Linkage

Check that Mosquitto is linked to the custom OpenSSL libraries:

```bash
ldd /opt/mosquitto-oqs/sbin/mosquitto | grep -E "ssl|crypto"
```

Expected result should show:

```text
/opt/openssl-3.5/lib/libssl.so.3
/opt/openssl-3.5/lib/libcrypto.so.3
```

If it shows `/usr/lib/...`, then Mosquitto is using the system OpenSSL instead of the custom OQS OpenSSL.

Also check the Mosquitto binary:

```bash
/opt/mosquitto-oqs/sbin/mosquitto -h
```

---

# 6. Add Library Paths

Create a linker config file:

```bash
sudo tee /etc/ld.so.conf.d/pqc-openssl.conf > /dev/null <<'EOF'
/opt/openssl-3.5/lib
/opt/openssl-3.5/lib64
/opt/mosquitto-oqs/lib
/opt/mosquitto-oqs/lib64
EOF
```

Update the linker cache:

```bash
sudo ldconfig
```

Check again:

```bash
ldd /opt/mosquitto-oqs/sbin/mosquitto | grep -E "ssl|crypto"
```

---

# 7. Create Mosquitto User and Folders

```bash
sudo groupadd -r mosquitto 2>/dev/null || true
sudo useradd -r -g mosquitto -d /var/lib/mosquitto -s /usr/sbin/nologin mosquitto 2>/dev/null || true

sudo mkdir -p /opt/mosquitto-oqs/config
sudo mkdir -p /opt/mosquitto-oqs/certs
sudo mkdir -p /var/lib/mosquitto
sudo mkdir -p /var/log/mosquitto

sudo chown -R mosquitto:mosquitto /var/lib/mosquitto
sudo chown -R mosquitto:mosquitto /var/log/mosquitto
```

---

# 8. Copy ML-DSA Certificates

This assumes the certificates are already generated inside:

```text
~/pqc-testbed/new_certs
```

Copy the CA certificate:

```bash
sudo cp ~/pqc-testbed/new_certs/ca/sit-ca.crt /opt/mosquitto-oqs/certs/sit-ca.crt
```

Copy the broker certificate and key:

```bash
sudo cp ~/pqc-testbed/new_certs/mosquitto/mqtt-broker.crt /opt/mosquitto-oqs/certs/mqtt-broker.crt
sudo cp ~/pqc-testbed/new_certs/mosquitto/mqtt-broker.key /opt/mosquitto-oqs/certs/mqtt-broker.key
```

Set permissions:

```bash
sudo chown -R mosquitto:mosquitto /opt/mosquitto-oqs/certs

sudo chmod 644 /opt/mosquitto-oqs/certs/sit-ca.crt
sudo chmod 644 /opt/mosquitto-oqs/certs/mqtt-broker.crt
sudo chmod 600 /opt/mosquitto-oqs/certs/mqtt-broker.key
```

Check the broker certificate algorithm:

```bash
OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf \
LD_LIBRARY_PATH=/opt/mosquitto-oqs/lib:/opt/mosquitto-oqs/lib64:/opt/openssl-3.5/lib:/opt/openssl-3.5/lib64 \
/opt/openssl-3.5/bin/openssl x509 \
  -in /opt/mosquitto-oqs/certs/mqtt-broker.crt \
  -noout -text | grep -E "Signature Algorithm|Public Key Algorithm|Subject:|Issuer:"
```

Expected output:

```text
Signature Algorithm: ML-DSA-44
Issuer: CN=SIT
Subject: CN=MQTT-Broker
Public Key Algorithm: ML-DSA-44
```

---

# 9. Create OpenSSL PQC Config

Open the OpenSSL PQC config file:

```bash
sudo nano /opt/mosquitto-oqs/config/openssl-pqc.cnf
```

Paste:

```conf
openssl_conf = openssl_init

[openssl_init]
providers = provider_sect
ssl_conf = ssl_sect

[provider_sect]
default = default_sect
oqsprovider = oqsprovider_sect

[default_sect]
activate = 1

[oqsprovider_sect]
activate = 1

[ssl_sect]
system_default = system_default_sect

[system_default_sect]
Groups = X25519MLKEM768:X25519:P-256
```

Save and exit.

Find the OQS provider module:

```bash
find /opt/openssl-3.5 -name "oqsprovider.so"
```

Possible result:

```text
/opt/openssl-3.5/lib64/ossl-modules/oqsprovider.so
```

or:

```text
/opt/openssl-3.5/lib/ossl-modules/oqsprovider.so
```

This path is needed later for the systemd service.

---

# 10. Create Mosquitto Config

Open the Mosquitto config file:

```bash
sudo nano /opt/mosquitto-oqs/config/mosquitto.conf
```

Paste:

```conf
per_listener_settings true

persistence true
persistence_location /var/lib/mosquitto/

log_dest stdout
log_type error
log_type warning
log_type notice
log_type information
connection_messages true

listener 8887 0.0.0.0
allow_anonymous false
require_certificate true
use_identity_as_username true

cafile /opt/mosquitto-oqs/certs/sit-ca.crt
certfile /opt/mosquitto-oqs/certs/mqtt-broker.crt
keyfile /opt/mosquitto-oqs/certs/mqtt-broker.key

tls_version tlsv1.3
ciphers DEFAULT:@SECLEVEL=0
```

Save and exit.

This config means:

```text
Port 8887 uses TLS 1.3.
The broker uses an ML-DSA certificate.
Clients must present a valid client certificate signed by the SIT CA.
```

---

# 11. Create Systemd Service

Open the service file:

```bash
sudo nano /etc/systemd/system/mosquitto-oqs.service
```

Paste:

```ini
[Unit]
Description=Custom OQS Mosquitto MQTT Broker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=mosquitto
Group=mosquitto

Environment="OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf"
Environment="OPENSSL_MODULES=/opt/openssl-3.5/lib64/ossl-modules"
Environment="LD_LIBRARY_PATH=/opt/mosquitto-oqs/lib:/opt/mosquitto-oqs/lib64:/opt/openssl-3.5/lib:/opt/openssl-3.5/lib64"

ExecStart=/opt/mosquitto-oqs/sbin/mosquitto -c /opt/mosquitto-oqs/config/mosquitto.conf

Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Save and exit.

If your `oqsprovider.so` is inside:

```text
/opt/openssl-3.5/lib/ossl-modules
```

instead of:

```text
/opt/openssl-3.5/lib64/ossl-modules
```

change this line:

```ini
Environment="OPENSSL_MODULES=/opt/openssl-3.5/lib64/ossl-modules"
```

to:

```ini
Environment="OPENSSL_MODULES=/opt/openssl-3.5/lib/ossl-modules"
```

---

# 12. Start Custom Mosquitto

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable the service:

```bash
sudo systemctl enable mosquitto-oqs
```

Start or restart the service:

```bash
sudo systemctl restart mosquitto-oqs
```

Check status:

```bash
sudo systemctl status mosquitto-oqs
```

Check logs:

```bash
sudo journalctl -u mosquitto-oqs -n 50 --no-pager
```

Check whether port `8887` is listening:

```bash
sudo ss -tanp | grep 8887
```

Expected:

```text
LISTEN 0 100 0.0.0.0:8887
```

---

# 13. Add Broker Hostname

The broker certificate uses the name `mqtt-broker`, so add this to `/etc/hosts`:

```bash
echo "192.168.1.50 mqtt-broker MQTT-Broker" | sudo tee -a /etc/hosts
```

Test:

```bash
getent hosts mqtt-broker
```

Expected:

```text
192.168.1.50 mqtt-broker MQTT-Broker
```

---

# 14. Test TLS 1.3 mTLS and Hybrid Key Exchange

Use the ESP32 ML-DSA client certificate for testing:

```bash
OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf \
LD_LIBRARY_PATH=/opt/mosquitto-oqs/lib:/opt/mosquitto-oqs/lib64:/opt/openssl-3.5/lib:/opt/openssl-3.5/lib64 \
/opt/openssl-3.5/bin/openssl s_client \
  -connect mqtt-broker:8887 \
  -servername mqtt-broker \
  -CAfile /opt/mosquitto-oqs/certs/sit-ca.crt \
  -cert ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.crt \
  -key ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.key \
  -groups X25519MLKEM768 \
  -tls1_3
```

Expected important lines:

```text
Verification: OK
Peer signature type: mldsa44
Negotiated TLS1.3 group: X25519MLKEM768
New, TLSv1.3
Verify return code: 0 (ok)
```

This proves:

```text
Broker ML-DSA certificate works.
Client ML-DSA certificate works.
mTLS works.
Hybrid X25519MLKEM768 works with the OQS/OpenSSL client.
```

---

# 15. Test MQTT Publish and Subscribe

Open Terminal 1 and subscribe:

```bash
OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf \
LD_LIBRARY_PATH=/opt/mosquitto-oqs/lib:/opt/mosquitto-oqs/lib64:/opt/openssl-3.5/lib:/opt/openssl-3.5/lib64 \
/opt/mosquitto-oqs/bin/mosquitto_sub \
  -h mqtt-broker \
  -p 8887 \
  --cafile /opt/mosquitto-oqs/certs/sit-ca.crt \
  --cert ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.crt \
  --key ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.key \
  -t "home/sensor/temp" \
  -d
```

Open Terminal 2 and publish:

```bash
OPENSSL_CONF=/opt/mosquitto-oqs/config/openssl-pqc.cnf \
LD_LIBRARY_PATH=/opt/mosquitto-oqs/lib:/opt/mosquitto-oqs/lib64:/opt/openssl-3.5/lib:/opt/openssl-3.5/lib64 \
/opt/mosquitto-oqs/bin/mosquitto_pub \
  -h mqtt-broker \
  -p 8887 \
  --cafile /opt/mosquitto-oqs/certs/sit-ca.crt \
  --cert ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.crt \
  --key ~/pqc-testbed/new_certs/esp32/esp32_mqtt_client.key \
  -t "home/sensor/temp" \
  -m '{"temperature_c":25.5}' \
  -d
```

Expected subscriber output:

```json
{"temperature_c":25.5}
```

---

# 16. Quick Rebuild Command

Use this when rebuilding Mosquitto later:

```bash
cd ~/pqc-testbed/src/mosquitto

rm -rf build

cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/mosquitto-oqs \
  -DCMAKE_PREFIX_PATH=/opt/openssl-3.5 \
  -DOPENSSL_ROOT_DIR=/opt/openssl-3.5 \
  -DOPENSSL_INCLUDE_DIR=/opt/openssl-3.5/include \
  -DOPENSSL_SSL_LIBRARY=/opt/openssl-3.5/lib/libssl.so \
  -DOPENSSL_CRYPTO_LIBRARY=/opt/openssl-3.5/lib/libcrypto.so \
  -DWITH_TLS=ON \
  -DWITH_TLS_PSK=ON \
  -DWITH_CJSON=ON \
  -DWITH_WEBSOCKETS=OFF \
  -DWITH_DOCS=OFF \
  -DWITH_TESTS=OFF

cmake --build build -j$(nproc)

sudo cmake --install build

sudo systemctl restart mosquitto-oqs
sudo systemctl status mosquitto-oqs
```

---

# 17. Verification Checklist

Use this checklist to confirm the broker is working:

```text
[ ] /opt/mosquitto-oqs/sbin/mosquitto exists
[ ] Mosquitto links to /opt/openssl-3.5/lib/libssl.so.3
[ ] Mosquitto links to /opt/openssl-3.5/lib/libcrypto.so.3
[ ] /opt/mosquitto-oqs/config/mosquitto.conf exists
[ ] /opt/mosquitto-oqs/config/openssl-pqc.cnf exists
[ ] /opt/mosquitto-oqs/certs/sit-ca.crt exists
[ ] /opt/mosquitto-oqs/certs/mqtt-broker.crt exists
[ ] /opt/mosquitto-oqs/certs/mqtt-broker.key exists
[ ] mosquitto-oqs.service is active
[ ] Port 8887 is listening
[ ] OpenSSL s_client verifies broker certificate
[ ] OpenSSL s_client shows Peer signature type: mldsa44
[ ] OpenSSL s_client shows Negotiated TLS1.3 group: X25519MLKEM768
[ ] mosquitto_pub and mosquitto_sub work over port 8887
```

---

# 18. Final Location Summary

```text
Mosquitto binary:
  /opt/mosquitto-oqs/sbin/mosquitto

Mosquitto clients:
  /opt/mosquitto-oqs/bin/mosquitto_sub
  /opt/mosquitto-oqs/bin/mosquitto_pub

Mosquitto config:
  /opt/mosquitto-oqs/config/mosquitto.conf

OpenSSL PQC config:
  /opt/mosquitto-oqs/config/openssl-pqc.cnf

Certificates:
  /opt/mosquitto-oqs/certs/

Systemd service:
  /etc/systemd/system/mosquitto-oqs.service
```
