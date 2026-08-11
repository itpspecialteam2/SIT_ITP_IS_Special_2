# Analysis and Enhancement of IoT Architecture by Quantum-Resistant Cryptography

## Project Overview

This project investigates the feasibility of retrofitting **post-quantum cryptography (PQC)** into a real-world IoT deployment. This project integrates NIST-standardized PQC — **ML-KEM** (key establishment) and **ML-DSA** (digital signatures) — into an MQTT and RTSP communication pipeline spanning a LoRaWAN gateway, a Jetson edge AI device, and a Raspberry Pi backend host.

### What the project accomplished
- Established a classical TLS baseline across every service (Home Assistant, Mosquitto, MediaMTX, go2rtc) before introducing PQC, to provide a fair performance/security comparison point.
- Recompiled **Mosquitto** from source against a custom-built **OpenSSL 3.5 + liboqs + OQS Provider** stack, making the MQTT broker natively PQC-capable.
- Bridged legacy/closed-firmware components (LoRaWAN gateway, go2rtc, Home Assistant) that cannot natively negotiate PQC, using **OQS-enabled HAProxy** as a transparent TLS-upgrading proxy.
- Built a project-specific **dual PKI**: a classical RSA CA for components without PQC support, and a separate ML-DSA-65 PQC CA for the OQS-enabled broker, reflecting the hybrid migration strategy.
- Implemented an **AES-256-CBC alternative uplink route** (`encrypt.py` / `decrypt.py`) for the LoRaWAN gateway, since its Python SDK's bundled OpenSSL 1.0.2k cannot negotiate TLS 1.3 or PQC directly.
- Benchmarked CPU/memory utilisation, TLS handshake overhead, and RTSP stream startup time across unsecured, classical-TLS, and PQC-TLS configurations, showing PQC introduces only a small overhead (e.g. ~5MB memory, ~0.16s stream startup) at the service level.
- Conducted adversarial testing (unsecured connection attempts, TLS version downgrade, classical cipher downgrade, PQC negotiation failure) across both the RTSP and MQTT paths, confirming the system **fails securely** with no silent fallback to weaker cryptography.

---

## Repository structure

- `jetson_nano` - edge AI device: occupancy detection + RTSP streaming + PQC tunnel endpoint
- `lorawan_gateway` - Milesight UG56 gateway: sensor uplink routes (classical + AES-256 alt route)
- `raspberry_pi` - central backend: MQTT broker, Home Assistant, go2rtc, PKI, proxies, benchmarking
- `HOTO.md` - documents IPs and ports in use, useful commands, etc
- `network_diagram.jpg` - diagram documenting overall network architecture

Each folder contains its own documentation and scripts, config files, etc.