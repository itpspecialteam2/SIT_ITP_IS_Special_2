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
