# download_pi_certs.py
# Run this script AFTER generate_internal_cert.py.
#
# What this does:
#   Downloads the three certificate files needed to connect to HAProxy
#   on the Raspberry Pi. Files are fetched via HTTP from a temporary
#   server running on the Pi.
#
# Before running this script:
#   On the Pi, start a temporary HTTP server in the certs directory:
#     cd /home/admin/Desktop/Project/mosquitto/certs
#     python3 -m http.server 9999
#   Stop it with Ctrl+C once this script completes.
#
# Note: SCP cannot be used because the gateway SSH shell outputs text
#   on connection which breaks SCP's protocol. wget via HTTP is the
#   correct transfer method.
#
# How to run:
#   1. SSH into the gateway
#   2. en
#   3. config t
#   4. python
#   5. debug download_pi_certs.py
#
# Expected output:
#   pi-ca.crt: OK
#   pi-gateway.crt: OK
#   pi-gateway.key: OK

import subprocess

# Change this if the Pi's IP address is different
PI_IP = "192.168.0.105"
PI_PORT = "9999"

files = [
    ("pi-ca.crt", "ca.crt"),
    ("pi-gateway.crt", "gateway.crt"),
    ("pi-gateway.key", "gateway.key")
]

for local_name, remote_name in files:
    url = "http://" + PI_IP + ":" + PI_PORT + "/" + remote_name
    dest = "/home/pyuser/certs/" + local_name

    r = subprocess.Popen(
        ['wget', '-O', dest, url],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = r.communicate()
    print(local_name + ":", "OK" if b'saved' in err else err[-200:])
