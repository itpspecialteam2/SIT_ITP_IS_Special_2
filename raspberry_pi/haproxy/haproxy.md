# HAProxy PQC Gateway

A HAProxy Docker container was deployed on the Raspberry Pi to provide a TLS termination and forwarding layer for communication between the **Jetson Orin Nano** and services hosted on the Raspberry Pi.

The HAProxy configuration was used as a proof of concept (POC) for:

* PQC-enabled TLS key exchange using `X25519MLKEM768`.
* TLS client/server certificate authentication.
* Encrypted communication between the Jetson Orin Nano and Raspberry Pi.
* Forwarding RTSP-over-TLS traffic to a HAProxy instance running on the Jetson.
* Forwarding MQTT-over-TLS traffic to the Mosquitto broker running on the Raspberry Pi.

The two main configured paths are:

```text
Jetson Orin Nano
      |
      | TLS 1.3
      | X25519MLKEM768
      v
Raspberry Pi HAProxy :18555
      |
      | TLS 1.3
      | X25519MLKEM768
      v
Jetson HAProxy :18554
```

and:

```text
Jetson / MQTT client
      |
      | TLS 1.3
      | X25519MLKEM768
      v
Raspberry Pi HAProxy :9993
      |
      | TLS 1.3
      | X25519MLKEM768
      v
Mosquitto :8883
```

## Docker deployment

HAProxy runs inside a Docker container on the Raspberry Pi.

```bash
docker ps
```

# HAProxy Configuration

See `./haproxy.cfg` for the full configuration used.

## Global configuration

### Logging

```haproxy
log stdout format raw local0
```

Sends HAProxy logs to standard output.

This is particularly useful in Docker because container logs can then be viewed using:

```bash
docker logs pqc-rtsp-pi
```

or:

```bash
docker logs -f pqc-rtsp-pi
```

### Maximum connections

```haproxy
maxconn 100
```

Limits HAProxy to a maximum of 100 simultaneous connections.

This value is suitable for a small POC but should be reviewed if the system is deployed in a larger environment.

### TLS version

```haproxy
ssl-default-server-options ssl-min-ver TLSv1.3 no-tls-tickets
```

Sets TLS 1.3 as the minimum TLS version for HAProxy's **backend server connections**.

`no-tls-tickets` disables TLS session tickets.

The explicit TLS 1.3 requirement is relevant to the PQC configuration because the configured `X25519MLKEM768` hybrid key-exchange group is being used with TLS 1.3.

### TLS cipher suites

```haproxy
ssl-default-server-ciphersuites TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256
```

Specifies the TLS 1.3 cipher suites that HAProxy may use for backend connections.

These are **symmetric encryption cipher suites** and are separate from the PQC key-exchange group.

In this configuration:

* `X25519MLKEM768` is the configured hybrid key-exchange group.
* `TLS_AES_256_GCM_SHA384`, `TLS_CHACHA20_POLY1305_SHA256`, and `TLS_AES_128_GCM_SHA256` are TLS 1.3 cipher suites.

# Defaults

```haproxy
defaults
    log global
    mode tcp
    option tcplog

    timeout connect 10s
    timeout client 1h
    timeout server 1h
```

### TCP mode

```haproxy
mode tcp
```

HAProxy operates at the TCP layer rather than interpreting the application protocol.

This is appropriate for the POC because the proxy is forwarding encrypted TLS traffic and does not need to inspect the RTSP or MQTT application payload.

### TCP logging

```haproxy
option tcplog
```

Enables HAProxy's TCP logging format, which provides connection-level information useful for troubleshooting.

### Timeouts

```haproxy
timeout connect 10s
timeout client 1h
timeout server 1h
```

`timeout connect` specifies how long HAProxy waits when establishing a connection to a backend server.

The client and server timeouts are set to one hour to accommodate long-lived connections.

This is particularly relevant to streaming or persistent MQTT connections, where connections may remain open for extended periods.

---

# RTSP TLS/PQC tunnel

## Frontend

```haproxy
frontend local_rtsps_in
    bind *:18555 ssl \
        crt /usr/local/etc/haproxy/certs/proxy-combined.pem \
        curves X25519MLKEM768:X25519:P-256:P-384

    default_backend pqc_tunnel_to_jetson
```

The frontend listens on port **18555** and accepts TLS connections from clients.

```haproxy
bind *:18555
```

means HAProxy listens on all available interfaces on port 18555.

### Server certificate

```haproxy
crt /usr/local/etc/haproxy/certs/proxy-combined.pem
```

Specifies the certificate/private-key bundle used by HAProxy for the TLS connection accepted by the frontend.

The certificate file must be available inside the HAProxy container at:

```text
/usr/local/etc/haproxy/certs/proxy-combined.pem
```

### Key-exchange groups

```haproxy
curves X25519MLKEM768:X25519:P-256:P-384
```

Specifies the supported TLS key-exchange groups in preference order.

The first option is:

```text
X25519MLKEM768
```

which is the hybrid post-quantum/classical key-exchange group used for the POC.

The remaining groups provide classical fallback options:

```text
X25519
P-256
P-384
```

This ordering makes `X25519MLKEM768` the preferred option when supported by the peer.

# RTSP backend

```haproxy
backend pqc_tunnel_to_jetson
    server jetson_pqc 192.168.0.106:18554 ssl \
        verify required \
        ca-file /usr/local/etc/haproxy/certs/jetson-mldsa65-ca.crt \
        curves X25519MLKEM768
```

This backend forwards traffic to the HAProxy instance running on the Jetson Orin Nano.

The Jetson endpoint is:

```text
192.168.0.106:18554
```

### TLS to Jetson

```haproxy
ssl
```

Enables TLS for the HAProxy-to-Jetson backend connection.

Therefore, TLS is used on the backend connection rather than forwarding the traffic as plaintext TCP.

### Certificate verification

```haproxy
verify required
```

Requires HAProxy to verify the certificate presented by the Jetson backend.

This is an important security setting because it prevents HAProxy from simply accepting any certificate from the backend.

### Private CA

```haproxy
ca-file /usr/local/etc/haproxy/certs/jetson-mldsa65-ca.crt
```

Specifies the CA certificate that HAProxy trusts when verifying the Jetson's server certificate.

The CA file must be available inside the HAProxy container.

### PQC backend key exchange

```haproxy
curves X25519MLKEM768
```

Restricts this backend TLS connection to the `X25519MLKEM768` key-exchange group.

Unlike the frontend, there are no classical fallback groups configured here.

Therefore, the backend connection is intended to require the PQC hybrid key exchange.

---

# MQTT / Mosquitto TLS/PQC tunnel

## Frontend

```haproxy
frontend mosquitto_in
    bind *:9993 ssl \
        crt /usr/local/etc/haproxy/certs/proxy-combined.pem \
        curves X25519MLKEM768:X25519:P-256:P-384

    default_backend mosquitto_pqc_out
```

This frontend accepts TLS connections on port **9993**.

The client connects to:

```text
19.168.0.105:9993
```

and HAProxy then forwards the connection to Mosquitto.

As with the RTSP frontend, the configured key-exchange preference is:

```text
X25519MLKEM768
X25519
P-256
P-384
```

The PQC hybrid group is preferred, but classical groups remain available as fallback.

---

# Mosquitto backend

```haproxy
backend mosquitto_pqc_out
    server mosquitto 127.0.0.1:8883 ssl \
        verify required \
        ca-file /usr/local/etc/haproxy/certs/mosquitto-oqs-ca.crt \
        curves X25519MLKEM768
```

This forwards traffic to the Mosquitto MQTT broker on port **8883**.

### Mosquitto certificate verification

```haproxy
verify required
ca-file /usr/local/etc/haproxy/certs/mosquitto-oqs-ca.crt
```

Requires HAProxy to validate Mosquitto's server certificate against the specified CA.

This provides certificate authentication for the backend connection.

### PQC key exchange

```haproxy
curves X25519MLKEM768
```

Requires the backend TLS connection to use `X25519MLKEM768`.

This means the intended HAProxy → Mosquitto connection uses the PQC hybrid key-exchange group rather than falling back to classical groups.

# Docker troubleshooting

View HAProxy logs:

```bash
docker logs pqc-rtsp-pi
```

Follow the logs:

```bash
docker logs -f pqc-rtsp-pi
```

Check the last 100 log lines:

```bash
docker logs --tail 100 pqc-rtsp-pi
```

Enter the container:

```bash
docker exec -it pqc-rtsp-pi /bin/sh
```

Check the certificate files:

```bash
docker exec pqc-rtsp-pi ls -la /usr/local/etc/haproxy/certs/
```
