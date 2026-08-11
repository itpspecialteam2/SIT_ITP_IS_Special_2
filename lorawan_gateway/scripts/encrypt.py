# -*- coding: utf-8 -*-
# encrypt.py
# AES-256 Encryption Bridge for IoT-PQC Project
# Singapore Institute of Technology - ITP Project IS1 Team IS Special 2
#
# Runs on: UG56 LoRaWAN Gateway (Python SDK)
#
# What this script does:
#   1. Subscribes to the gateway's internal Mosquitto broker on port 18883
#   2. Receives decoded sensor JSON from all LoRaWAN devices
#   3. Encrypts each payload using AES-256-CBC with a pre-shared key
#   4. Publishes the encrypted payload to HAProxy on the Pi over TLS 1.2
#      HAProxy then forwards to Mosquitto over PQ TLS 1.3 (X25519MLKEM768)
#
# Note: The gateway Python SDK is limited to TLS 1.2 due to its bundled
# OpenSSL 1.0.2k (released 2017, predates TLS 1.3). HAProxy on the Pi
# bridges this to PQ TLS 1.3 on the broker side.
#
# The AES_KEY must match decrypt.py on the Pi exactly.

import ctypes
import os
import base64
import ssl
import time
import paho.mqtt.client as mqtt

# =============================================================================
# AES-256 ENCRYPTION SETUP
# Uses libcrypto.so via ctypes since no third-party crypto library
# is available in the gateway's Python 2.7 SDK environment
# =============================================================================

libcrypto = ctypes.CDLL('libcrypto.so')

libcrypto.EVP_CIPHER_CTX_new.restype = ctypes.c_void_p
libcrypto.EVP_aes_256_cbc.restype = ctypes.c_void_p
libcrypto.EVP_EncryptInit_ex.restype = ctypes.c_int
libcrypto.EVP_EncryptUpdate.restype = ctypes.c_int
libcrypto.EVP_EncryptFinal_ex.restype = ctypes.c_int
libcrypto.EVP_CIPHER_CTX_free.restype = None

# Pre-shared key - 32 bytes = 256 bits
# Must match AES_KEY in decrypt.py on the Pi exactly
AES_KEY = b'SIT-ProjectIS1-PQC-AES256-Key12345'

def encrypt_aes256(plaintext, key):
    """
    Encrypt plaintext using AES-256-CBC via libcrypto EVP interface.
    Output format: base64( IV (16 bytes) + ciphertext )
    """
    iv = os.urandom(16)
    ctx = libcrypto.EVP_CIPHER_CTX_new()
    cipher = libcrypto.EVP_aes_256_cbc()
    libcrypto.EVP_EncryptInit_ex(
        ctypes.c_void_p(ctx), ctypes.c_void_p(cipher),
        None, ctypes.c_char_p(key), ctypes.c_char_p(iv))
    plaintext_bytes = plaintext.encode('utf-8') if isinstance(plaintext, unicode) else plaintext
    out_buf = ctypes.create_string_buffer(len(plaintext_bytes) + 16)
    out_len = ctypes.c_int(0)
    libcrypto.EVP_EncryptUpdate(
        ctypes.c_void_p(ctx), out_buf, ctypes.byref(out_len),
        ctypes.c_char_p(plaintext_bytes), ctypes.c_int(len(plaintext_bytes)))
    encrypted = out_buf.raw[:out_len.value]
    final_buf = ctypes.create_string_buffer(16)
    final_len = ctypes.c_int(0)
    libcrypto.EVP_EncryptFinal_ex(
        ctypes.c_void_p(ctx), final_buf, ctypes.byref(final_len))
    encrypted += final_buf.raw[:final_len.value]
    libcrypto.EVP_CIPHER_CTX_free(ctypes.c_void_p(ctx))
    return base64.b64encode(iv + encrypted)

# =============================================================================
# MQTT CONFIGURATION
# =============================================================================

# Internal gateway broker - where the embedded network server
# publishes decoded LoRaWAN sensor data
INTERNAL_BROKER = "127.0.0.1"
INTERNAL_PORT   = 18883
INTERNAL_CA     = "/home/pyuser/certs/ca-mqtt.crt"
INTERNAL_CERT   = "/home/pyuser/certs/client.crt"
INTERNAL_KEY    = "/home/pyuser/certs/client.key"

# HAProxy on the Pi - accepts TLS 1.2 from gateway,
# upgrades to PQ TLS 1.3 (X25519MLKEM768) towards Mosquitto
EXTERNAL_BROKER = "192.168.0.105"
EXTERNAL_PORT   = 9993
EXTERNAL_CA     = "/home/pyuser/certs/pi-ca.crt"
EXTERNAL_CERT   = "/home/pyuser/certs/pi-gateway.crt"
EXTERNAL_KEY    = "/home/pyuser/certs/pi-gateway.key"

# Subscribe to all LoRaWAN device uplink topics on internal broker
INTERNAL_TOPIC = "application/2/device/+/rx"

# Publish encrypted payloads to this topic prefix on external broker
EXTERNAL_TOPIC_PREFIX = "milesight/encrypted"

# =============================================================================
# PUBLISHER CLIENT - connects to HAProxy on Pi
# =============================================================================

publisher = mqtt.Client(client_id="gateway-aes-publisher")

def on_publisher_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[PUBLISHER] Connected to HAProxy on Pi")
    else:
        print("[PUBLISHER] Failed to connect, rc:", rc)

def on_publisher_disconnect(client, userdata, rc):
    print("[PUBLISHER] Disconnected from Pi, rc:", rc)

publisher.on_connect = on_publisher_connect
publisher.on_disconnect = on_publisher_disconnect

# =============================================================================
# SUBSCRIBER CLIENT - connects to internal gateway broker
# =============================================================================

def on_internal_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[SUBSCRIBER] Connected to internal gateway broker")
        client.subscribe(INTERNAL_TOPIC)
        print("[SUBSCRIBER] Subscribed to:", INTERNAL_TOPIC)
    else:
        print("[SUBSCRIBER] Failed to connect to internal broker, rc:", rc)

def on_internal_message(client, userdata, msg):
    """
    Called when a sensor message arrives on the internal broker.
    Encrypts the payload and forwards it to the Pi via HAProxy.
    """
    try:
        payload = msg.payload
        topic = msg.topic

        # Extract device EUI from topic
        # Topic format: application/2/device/<devEUI>/rx
        parts = topic.split('/')
        dev_eui = parts[3] if len(parts) >= 4 else 'unknown'

        # Encrypt payload with AES-256
        encrypted = encrypt_aes256(payload, AES_KEY)

        # Publish encrypted payload to external broker
        out_topic = EXTERNAL_TOPIC_PREFIX + "/" + dev_eui
        publisher.publish(out_topic, encrypted, qos=1)

        print("[BRIDGE] " + topic + " -> " + out_topic)
        print("[BRIDGE] Original length:", len(payload),
              "Encrypted length:", len(encrypted))

    except Exception as e:
        print("[BRIDGE] Error processing message:", e)

def on_internal_disconnect(client, userdata, rc):
    print("[SUBSCRIBER] Disconnected from internal broker, rc:", rc)

subscriber = mqtt.Client(client_id="gateway-aes-subscriber")
subscriber.on_connect = on_internal_connect
subscriber.on_message = on_internal_message
subscriber.on_disconnect = on_internal_disconnect

# =============================================================================
# MAIN
# =============================================================================

print("Starting AES-256 Encryption Bridge...")
print("Internal broker : %s:%d" % (INTERNAL_BROKER, INTERNAL_PORT))
print("HAProxy on Pi   : %s:%d" % (EXTERNAL_BROKER, EXTERNAL_PORT))
print("AES key length  : %d bytes (%d bits)" % (len(AES_KEY), len(AES_KEY) * 8))

# Connect publisher to HAProxy on Pi over TLS 1.2
try:
    publisher.tls_set(
        ca_certs=EXTERNAL_CA,
        certfile=EXTERNAL_CERT,
        keyfile=EXTERNAL_KEY
    )
    publisher.tls_insecure_set(True)
    publisher.connect(EXTERNAL_BROKER, EXTERNAL_PORT, 60)
    publisher.loop_start()
    print("[PUBLISHER] Connecting to HAProxy on Pi...")
except Exception as e:
    print("[PUBLISHER] Connection error:", e)

# Connect subscriber to internal gateway broker over TLS 1.2
try:
    subscriber.tls_set(
        ca_certs=INTERNAL_CA,
        certfile=INTERNAL_CERT,
        keyfile=INTERNAL_KEY,
        tls_version=ssl.PROTOCOL_TLSv1_2
    )
    subscriber.tls_insecure_set(True)
    subscriber.connect(INTERNAL_BROKER, INTERNAL_PORT, 60)
    subscriber.loop_start()
    print("[SUBSCRIBER] Connecting to internal broker...")
except Exception as e:
    print("[SUBSCRIBER] Connection error:", e)

# Run indefinitely
print("Running...")
while True:
    time.sleep(60)
