# Nginx Reverse Proxy for PQC-Enabled TLS

An Nginx reverse proxy was configured on **port 8124** as a proof of concept (POC) for providing PQC-enabled TLS connectivity between external web browsers and the Home Assistant (HA) web server.

Home Assistant is normally accessible on **port 8123** and, in the current setup, already supports PQC-enabled TLS without requiring Nginx. Therefore, the Nginx proxy is not required for HA itself. Instead, it demonstrates how a reverse proxy could be used to add PQC support in front of a web server that does not natively support the required PQC key-exchange algorithms.

The proxy also provides a potential architecture for **PQC client authentication** at the proxy layer. HA itself does not currently provide PQC authentication. However, implementing this architecture for external browsers would require an additional client-side component, as modern browsers do not currently provide native support for PQC client authentication.

The resulting connection path is:

```text
External Browser
       |
       |  TLS 1.3 + X25519MLKEM768
       |  HTTPS :8124
       v
+------------------+
| Nginx Proxy      |
| Raspberry Pi     |
| :8124            |
+------------------+
       |
       | HTTPS :8123
       v
+------------------+
| Home Assistant   |
| Web Server       |
| :8123            |
+------------------+
```

## WebSocket support

Home Assistant uses WebSockets for parts of its web interface. Nginx therefore needs to be configured to support the **HTTP/1.1 WebSocket upgrade mechanism**.

The `map` directive creates a `$connection_upgrade` variable based on the client's `Upgrade` header. The proxy then forwards the `Upgrade` and `Connection` headers to HA so that HTTP connections can be upgraded to WebSocket connections when required.

Without these settings, the HA web interface may load but WebSocket-dependent functionality can fail or disconnect.

## Installation

On Raspberry Pi OS, install Nginx using the system package manager:

```bash
sudo apt update
sudo apt install nginx
```

Check that Nginx was installed successfully:

```bash
nginx -v
```

Enable Nginx to start automatically at boot and start the service:

```bash
sudo systemctl enable nginx
sudo systemctl start nginx
```

Check its status:

```bash
sudo systemctl status nginx
```

If Nginx is already running, use:

```bash
sudo systemctl restart nginx
```

## Directory setup

Create a directory for the TLS certificate and private key:

```bash
sudo mkdir -p /etc/nginx/certs
```

Place the proxy certificate and private key in this directory:

```text
/etc/nginx/certs/proxy.crt
/etc/nginx/certs/proxy.key
```

The private key should have appropriately restrictive permissions. For example:

```bash
sudo chmod 600 /etc/nginx/certs/proxy.key
```

Ensure that the Nginx configuration references the correct certificate and key paths.

## Configuration

See `./nginx.conf` for the full configuration used.

## Testing the configuration

Before applying a configuration change, test the Nginx configuration syntax:

```bash
sudo nginx -t
```

A successful test should report that the configuration syntax is OK and that the configuration test is successful.

Reload Nginx without completely stopping the service:

```bash
sudo systemctl reload nginx
```

If the configuration test fails, check the error message and inspect the Nginx error log:

```bash
sudo tail -f /var/log/nginx/error.log
```

The service status can also be checked with:

```bash
sudo systemctl status nginx
```

## Troubleshooting checklist

If the proxy is not working:

1. Confirm that HA is running and listening on port 8123.
2. Confirm that Nginx is running and listening on port 8124.
3. Run `sudo nginx -t` to check the configuration.
4. Check `/var/log/nginx/error.log`.
5. Confirm that the TLS certificate and private key exist at the configured paths.
6. Confirm that the installed OpenSSL/Nginx versions support `X25519MLKEM768`.
7. Check that WebSocket upgrade headers are being passed correctly.
8. If the backend TLS connection fails, check the HA certificate configuration and the `proxy_ssl_*` settings.
9. If external clients cannot connect, check the Raspberry Pi firewall/network configuration and confirm that port 8124 is reachable.

### Useful commands

```bash
# Check Nginx version
nginx -v

# Check Nginx configuration
sudo nginx -t

# Start Nginx
sudo systemctl start nginx

# Stop Nginx
sudo systemctl stop nginx

# Restart Nginx
sudo systemctl restart nginx

# Reload configuration
sudo systemctl reload nginx

# Check service status
sudo systemctl status nginx

# View recent error messages
sudo tail -n 50 /var/log/nginx/error.log

# Follow the error log in real time
sudo tail -f /var/log/nginx/error.log
```
