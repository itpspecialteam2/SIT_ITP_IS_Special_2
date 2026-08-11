## Security Validation – Jetson Orin Nano RTSP

Security validation was performed on the Jetson Orin Nano RTSP communication path to verify that video streams require encrypted communication and that the configured TLS and PQC security policies are enforced.

**Unsecured RTSP:** A secure RTSPS connection was first established using FFplay to confirm that the stream was functioning correctly. An unsecured RTSP connection was then attempted using the same stream endpoint. The RTSPS connection succeeded while the unsecured RTSP connection was rejected, confirming that plaintext RTSP traffic is not permitted.

**TLS Downgrade:** An OpenSSL client was used to connect to the HAProxy TLS endpoint on port 18554 while forcing TLS 1.2 using `openssl s_client -connect <JETSON_IP>:18554 -tls1_2`. The connection was rejected with SSL Alert 70 (Protocol Version), confirming that TLS 1.2 cannot be negotiated and that TLS 1.3 is enforced.

**PQC Negotiation Failure:** An OpenSSL client was used to attempt a TLS 1.3 connection to the PQC-enabled RTSP service without the required PQC parameters. The connection failed with SSL Alert 40 (Handshake Failure), confirming that unsupported clients are rejected rather than falling back to a classical cryptographic configuration.

These results validate that the Jetson Orin Nano RTSP path enforces encrypted communication, TLS 1.3, and the required PQC configuration without insecure fallback.
