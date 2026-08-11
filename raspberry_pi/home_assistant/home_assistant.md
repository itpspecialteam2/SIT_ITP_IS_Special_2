# Home Assistant Docker Configuration

Home Assistant (HA) is deployed as a Docker container. The HA web interface is exposed on port **8123**.

The current setup uses Nginx as an additional reverse-proxy POC on port **8124**. Nginx terminates the external HTTPS connection and proxies requests to the Home Assistant container.

```text
External browser
       |
       | HTTPS :8124
       v
    Nginx
       |
       | HTTPS :8123
       v
Home Assistant
   Docker container
```

## MQTT configuration

The MQTT broker (Mosquitto) is configured through the Home Assistant web interface.

To change the MQTT broker IP address or port:

1. Open Home Assistant. (https://192.168.0.105:8123/)
2. Go to **Settings → Devices & services**.
3. Select **MQTT**.
4. Click the **three-dot menu**.
5. Select **Reconfigure**.
6. Enter the Mosquitto broker IP address and port as required.

## Home Assistant configuration.yaml

The following configuration was added to support TLS/HTTPS and to allow Home Assistant to correctly process requests forwarded through the Nginx reverse proxy.

```yaml
additional_ca:
  my_private_ca: ca.crt

http:
  ssl_certificate: /config/ssl/fullchain.pem
  ssl_key: /config/ssl/privkey.pem
  use_x_forwarded_for: true
  trusted_proxies:
    - 127.0.0.1
    - ::1
```

### Private CA

```yaml
additional_ca:
  my_private_ca: ca.crt
```

Adds the project's private CA certificate to Home Assistant's trusted certificate authorities.

## HTTPS configuration

```yaml
http:
  ssl_certificate: /config/ssl/fullchain.pem
  ssl_key: /config/ssl/privkey.pem
```

These directives configure Home Assistant's built-in web server to use HTTPS.

`ssl_certificate` specifies the certificate chain presented by Home Assistant.

`ssl_key` specifies the corresponding private key.

## Reverse-proxy support

Because Nginx sits in front of Home Assistant, HA receives some requests from the proxy rather than directly from the original browser.

```yaml
use_x_forwarded_for: true
```

Enables Home Assistant to use the `X-Forwarded-For` header to determine the original client IP address.

The proxy must be trusted before Home Assistant will accept forwarded client information.

```yaml
trusted_proxies:
  - 127.0.0.1
  - ::1
```

Specifies the proxy IP addresses that Home Assistant is allowed to trust when processing forwarded headers.

# Home Assistant Docker Management

## Check running containers

```bash
docker ps
```

## View Home Assistant logs

```bash
docker logs homeassistant
```

Follow the logs in real time:

```bash
docker logs -f homeassistant
```

Show only the most recent lines:

```bash
docker logs --tail 100 homeassistant
```

## Restart Home Assistant

```bash
docker restart homeassistant
```

Check its status afterwards:

```bash
docker ps --filter "name=homeassistant"
```

## Start and stop the container

```bash
docker start homeassistant
```

```bash
docker stop homeassistant
```

## Inspect the container

Useful when troubleshooting networking, volumes, or environment configuration:

```bash
docker inspect homeassistant
```

## Open a shell inside the container

```bash
docker exec -it homeassistant /bin/bash
```

# Troubleshooting checklist

### Home Assistant is unreachable

Check whether the container is running:

```bash
docker ps --filter "name=homeassistant"
```

Check its logs:

```bash
docker logs --tail 100 homeassistant
```

Check which ports are exposed:

```bash
docker port homeassistant
```

### HTTPS does not work

Verify that the certificate files exist inside the container:

```bash
docker exec homeassistant ls -l /config/ssl/
```

Check that the configured filenames match:

```text
/config/ssl/fullchain.pem
/config/ssl/privkey.pem
```

Check the Home Assistant logs for certificate, key, or TLS errors.

### Nginx gives a 400/403 error from Home Assistant

Check the `trusted_proxies` configuration.

The IP address seen by Home Assistant for Nginx must be included in `trusted_proxies`.

Inspect the Docker network configuration:

```bash
docker inspect homeassistant --format '{{json .NetworkSettings.Networks}}'
```

### WebSocket functionality does not work

Check that Nginx has:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
```

Also check the Nginx error log:

```bash
sudo tail -f /var/log/nginx/error.log
```

and the Home Assistant container logs:

```bash
docker logs -f homeassistant
```

### Certificate files are missing

Check the host-to-container volume mapping:

```bash
docker inspect homeassistant --format '{{range .Mounts}}{{println .Source "->" .Destination}}{{end}}'
```

Then verify the files from inside the container:

```bash
docker exec homeassistant ls -la /config/ssl/
```

If the files exist on the host but not inside `/config/ssl/`, the Docker volume/bind-mount configuration needs to be checked.