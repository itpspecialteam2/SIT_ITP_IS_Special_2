# verify_certs.py
# Run this script after setup_certs.py, generate_internal_cert.py,
# and download_pi_certs.py to confirm all required files are present.
#
# What this does:
#   Checks that all six certificate files required by encrypt.py
#   exist in /home/pyuser/certs/. Reports EXISTS or MISSING for each.
#
# How to run:
#   1. SSH into the gateway
#   2. en
#   3. config t
#   4. python
#   5. debug verify_certs.py
#
# Expected output:
#   /home/pyuser/certs/pi-ca.crt       EXISTS
#   /home/pyuser/certs/pi-gateway.crt  EXISTS
#   /home/pyuser/certs/pi-gateway.key  EXISTS
#   /home/pyuser/certs/client.crt      EXISTS
#   /home/pyuser/certs/client.key      EXISTS
#   /home/pyuser/certs/ca-mqtt.crt     EXISTS
#   All certificates present. Ready to run encrypt.py

import os

required_files = [
    '/home/pyuser/certs/pi-ca.crt',
    '/home/pyuser/certs/pi-gateway.crt',
    '/home/pyuser/certs/pi-gateway.key',
    '/home/pyuser/certs/client.crt',
    '/home/pyuser/certs/client.key',
    '/home/pyuser/certs/ca-mqtt.crt',
]

all_present = True

for f in required_files:
    status = "EXISTS" if os.path.exists(f) else "MISSING"
    if status == "MISSING":
        all_present = False
    print(f, status)

if all_present:
    print("All certificates present. Ready to run encrypt.py")
else:
    print("Some certificates are missing. Check TROUBLESHOOTING.md")
