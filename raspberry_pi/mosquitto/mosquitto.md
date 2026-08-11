# Mosquitto PQC Configuration

Eclipse Mosquitto was recompiled with **OpenSSL 3.5** and the **OQS provider** to enable PQC support. Refer to [`./MQTT_Broker_Installation.md`](./MQTT_Broker_Installation.md) for the installation and recompilation procedure.

Mosquitto runs as a `systemctl` service and is configured to support TLS 1.3 with the `X25519MLKEM768` PQC hybrid key-exchange group.

## mosquitto.conf

See `./mosquitto.conf` for the full configuration used.

The broker listens for TLS connections on port **8883**. TLS 1.3 is enforced using:

```conf
tls_version tlsv1.3
```

The `cafile`, `certfile`, and `keyfile` specify the CA certificate, broker certificate, and corresponding private key used for TLS.

For this POC, anonymous MQTT connections are permitted and client certificate authentication is disabled:

```conf
allow_anonymous true
require_certificate false
```

Therefore, the TLS connection provides server authentication and PQC key exchange, but does not require clients to authenticate using a client certificate.

## OpenSSL PQC configuration

Mosquitto is started with an OpenSSL configuration file, `openssl-pqc.cnf`, which loads the OQS provider and configures `X25519MLKEM768` as the preferred TLS key-exchange group.

The OQS provider is enabled with:

```conf
oqsprovider = oqsprovider_sect

[oqsprovider_sect]
activate = 1
```

The TLS configuration then specifies:

```conf
Groups = X25519MLKEM768
```

This configures OpenSSL to use the `X25519MLKEM768` hybrid key-exchange group, combining classical X25519 with the post-quantum ML-KEM-768 algorithm.

The OpenSSL configuration must be loaded when Mosquitto starts. The systemd service configuration should therefore set the appropriate OpenSSL configuration environment variable, for example:

```text
OPENSSL_CONF=/opt/mosquitto-oqs/openssl-pqc.cnf
```

The exact location and service configuration should match the installation described in `MQTT_Broker_Installation.md`.

## Service management

Check the Mosquitto service:

```bash
sudo systemctl status mosquitto
```

Restart after configuration changes:

```bash
sudo systemctl restart mosquitto
```

View logs:

```bash
sudo journalctl -u mosquitto -f
```

Check that the broker is listening on port 8883:

```bash
sudo ss -lntp | grep 8883
```