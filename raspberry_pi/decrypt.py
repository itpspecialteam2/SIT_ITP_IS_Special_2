#!/usr/bin/env python3
"""
decrypt.py
AES-256 Decryption Bridge for IoT-PQC Project
Singapore Institute of Technology - ITP Project IS1 Team IS Special 2

Runs on: Raspberry Pi (central host)

What this script does:
  1. Subscribes to milesight/encrypted/# on the Mosquitto broker
  2. Decrypts each payload using AES-256-CBC with a pre-shared key
  3. Extracts only the sensor object to match the primary firmware format
  4. Republishes the decrypted sensor object to milesight/uplink/<devEUI>
     which Home Assistant subscribes to for sensor state updates

The AES_KEY must match encrypt.py on the gateway exactly.

Usage:
    python3 decrypt.py

Run as a background service:
    nohup python3 decrypt.py &
"""

import paho.mqtt.client as mqtt
import ssl
import base64
import json
import sys
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# =============================================================================
# CONFIGURATION
# =============================================================================

# Pre-shared AES-256 key - must match encrypt.py on the gateway exactly
# 32 bytes = 256 bits
AES_KEY = b'SIT-ProjectIS1-PQC-AES256-Key12345'

# Mosquitto broker on the Pi
# decrypt.py connects directly to Mosquitto using PQC certificates
BROKER_HOST = "localhost"
BROKER_PORT = 8883

# PQC certificate paths - signed by the ML-DSA-65 CA
# used by the OQS-enabled Mosquitto broker
CA_CERT     = "/home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/ca.crt"
CLIENT_CERT = "/home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.crt"
CLIENT_KEY  = "/home/admin/Desktop/IS_2/mosquitto-oqs-setup/certs/mldsa65/decrypt-bridge.key"

# Topics
ENCRYPTED_TOPIC  = "milesight/encrypted/#"  # incoming encrypted payloads
DECRYPTED_PREFIX = "milesight/uplink"        # outgoing decoded sensor objects

# =============================================================================
# AES-256 DECRYPTION
# =============================================================================

def decrypt_aes256(encrypted_b64, key):
    """
    Decrypt AES-256-CBC ciphertext produced by encrypt.py on the gateway.

    Input format: base64( IV (16 bytes) + ciphertext )
    Returns: decrypted plaintext as UTF-8 string
    """
    raw = base64.b64decode(encrypted_b64)
    iv = raw[:16]
    ciphertext = raw[16:]

    cipher = Cipher(
        algorithms.AES(key),
        modes.CBC(iv),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()

    # Remove PKCS7 padding
    pad_len = padded[-1] if isinstance(padded[-1], int) else ord(padded[-1])
    return padded[:-pad_len].decode('utf-8')

# =============================================================================
# MQTT CLIENT
# =============================================================================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[BRIDGE] Connected to Mosquitto broker")
        client.subscribe(ENCRYPTED_TOPIC)
        print("[BRIDGE] Subscribed to:", ENCRYPTED_TOPIC)
    else:
        print("[BRIDGE] Failed to connect, rc:", rc)

def on_message(client, userdata, msg):
    try:
        # Extract device EUI from topic
        # Topic format: milesight/encrypted/<devEUI>
        parts = msg.topic.split('/')
        dev_eui = parts[2] if len(parts) >= 3 else 'unknown'

        # Decrypt AES-256 payload
        decrypted = decrypt_aes256(msg.payload, AES_KEY)

        # Parse full JSON and extract only the sensor object
        # This matches the format published by the primary firmware route
        # e.g. {"battery":80,"co2":366,"humidity":56.5,"temperature":24}
        full_payload = json.loads(decrypted)
        sensor_object = full_payload.get('object', full_payload)
        output = json.dumps(sensor_object)

        # Republish decoded sensor object to milesight/uplink/<devEUI>
        out_topic = DECRYPTED_PREFIX + "/" + dev_eui
        client.publish(out_topic, output, qos=1)

        preview = output[:80] + "..." if len(output) > 80 else output
        print("[BRIDGE] Decrypted %s -> %s" % (msg.topic, out_topic))
        print("[BRIDGE] Payload: %s" % preview)

    except Exception as e:
        print("[BRIDGE] Error processing message on topic %s: %s" % (msg.topic, e))

def on_disconnect(client, userdata, rc):
    print("[BRIDGE] Disconnected, rc:", rc)
    if rc != 0:
        print("[BRIDGE] Unexpected disconnect - will attempt reconnect")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print(" AES-256 Decryption Bridge")
    print(" SIT IoT-PQC Project")
    print("=" * 60)
    print(" Broker     : %s:%d" % (BROKER_HOST, BROKER_PORT))
    print(" Subscribe  : %s" % ENCRYPTED_TOPIC)
    print(" Republish  : %s/<devEUI>" % DECRYPTED_PREFIX)
    print(" AES key    : %d bytes (%d bits)" % (len(AES_KEY), len(AES_KEY) * 8))
    print(" Output fmt : sensor object only (matches primary firmware)")
    print("=" * 60)

    client = mqtt.Client(client_id="pi-aes-decrypt-bridge")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    # Connect directly to Mosquitto using PQC ML-DSA-65 certificates
    client.tls_set(
        ca_certs=CA_CERT,
        certfile=CLIENT_CERT,
        keyfile=CLIENT_KEY,
        tls_version=ssl.PROTOCOL_TLS
    )
    client.tls_insecure_set(True)

    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
        print("[BRIDGE] Starting - press Ctrl+C to stop")
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[BRIDGE] Stopped by user")
        client.disconnect()
    except Exception as e:
        print("[BRIDGE] Fatal error:", e)
        sys.exit(1)

if __name__ == "__main__":
    main()
