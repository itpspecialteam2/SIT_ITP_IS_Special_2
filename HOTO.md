# Devices
| device          | IP            | user       | pass        |
| --------------- | ------------- | ---------- | ----------- |
| TP Link router  | 192.168.0.1   | -          | admin123456 |
| LoRaWan Gateway | 192.168.0.102 | admin      | MileSight14 |
| Raspberry Pi    | 192.168.0.105 | admin      | admin       |
| Jetson          | 192.168.0.106 | jetsonorin | password    |

# Raspberry Pi services (all Docker containers except Mosquitto)

| service        | listen port          | config filepath(s)                                                                    | user/pass   |
| -------------- | -------------------- | ------------------------------------------------------------------------------------- | ----------- |
| Home Assistant | 8123                 | /home/admin/Desktop/Project/config/configuration.yaml                                 | admin/admin |
| Nginx          | 8124                 | /etc/nginx/nginx.conf                                                                 | -           |
| Mosquitto      | 8883                 | /opt/mosquitto-oqs/config/mosquitto.conf<br>/opt/mosquitto-oqs/config/openssl-pqc.cnf | -           |
| HAProxy        | 18555 9993           | /home/admin/pqc-rtsp/pi-proxy/haproxy.cfg                                             | -           |
| go2rtc         | 1984<br>8554<br>8555 | /home/admin/Desktop/Project/go2rtc/go2rtc.yaml                                        | -           |

# Handover Notes

1. **Known limitations to be aware of**:
   - LoRaWAN radio link (sensor → gateway) is AES-128 only — outside current PQC scope.
   - Home Assistant and go2rtc support PQ key exchange but **not** PQ authentication (their bundled OpenSSL doesn't support ML-DSA) — they rely on HAProxy/Nginx for PQ authentication.
   - The LoRaWAN gateway's Python SDK is bundled with OpenSSL 1.0.2k — the AES-256 bridge route exists specifically to work around this.
2. **Suggested next steps**:
   - Recompile Home Assistant and go2rtc natively against a PQC-enabled OpenSSL build, removing the need for the proxy layer.
   - Explore more open/programmable LoRaWAN hardware (e.g. a Raspberry Pi as a software-defined LoRaWAN end-node or gateway via ChirpStack) to extend the quantum-safe boundary down to the sensor layer.