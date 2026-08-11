## Security Validation – LoRaWAN Gateway to MQTT

Security validation was performed on the LoRaWAN Gateway-to-MQTT communication path to verify that TLS 1.3 and the required PQC configuration are enforced without allowing insecure fallback.

**TLS Downgrade:** An OpenSSL client was used to connect to the MQTT broker on port 8883 while forcing TLS 1.2 using `openssl s_client -connect <MQTT_IP>:8883 -tls1_2`. The connection was rejected with SSL Alert 70 (Protocol Version), confirming that older TLS versions are not accepted.

**PQC Negotiation Failure:** An OpenSSL client was used to attempt a TLS 1.3 connection without the required PQC negotiation parameters using `openssl s_client -connect <MQTT_IP>:8883 -tls1_3`. The connection failed with SSL Alert 40 (Handshake Failure), confirming that clients unable to satisfy the PQC requirements are rejected instead of falling back to classical TLS.

These results validate that the LoRaWAN Gateway-to-MQTT communication path enforces the intended TLS and PQC security policies and prevents downgrade or insecure fallback attempts.
