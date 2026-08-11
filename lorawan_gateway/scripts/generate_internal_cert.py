# generate_internal_cert.py
# Run this script AFTER setup_certs.py.
#
# What this does:
#   1. Copies the internal gateway CA cert and key from /etc/ssl/certs/
#      to /home/pyuser/certs/ (writable location)
#   2. Generates a private key for the Python bridge client
#   3. Generates a certificate signing request (CSR)
#   4. Signs the CSR with the internal CA to produce client.crt
#
# The resulting client.crt and client.key are used by encrypt.py
# to authenticate to the gateway's internal Mosquitto broker on port 18883.
#
# How to run:
#   1. SSH into the gateway
#   2. en
#   3. config t
#   4. python
#   5. debug generate_internal_cert.py
#
# Expected output:
#   cp ca-mqtt.crt: OK
#   cp ca-mqtt.key: OK
#   Key: OK
#   CSR: OK
#   Sign: Signature ok ...
#   Verify: subject= /CN=lorawan/O=gateway/C=SG

import subprocess

# Step 1 - Copy internal CA to writable location
# Cannot sign from /etc/ssl/certs/ directly as it is read-only
# (serial file write would fail with Permission denied)
for src, dst in [
    ('/etc/ssl/certs/ca-mqtt.crt', '/home/pyuser/certs/ca-mqtt.crt'),
    ('/etc/ssl/certs/ca-mqtt.key', '/home/pyuser/certs/ca-mqtt.key'),
]:
    r = subprocess.Popen(
        ['cp', src, dst],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = r.communicate()
    print("cp " + dst.split('/')[-1] + ":", err if err else "OK")

# Step 2 - Generate private key for the bridge client
r = subprocess.Popen(
    ['openssl', 'genrsa', '-out', '/home/pyuser/certs/client.key', '2048'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("Key:", "OK" if not err or b'error' not in err.lower() else err)

# Step 3 - Generate certificate signing request
r = subprocess.Popen(
    ['openssl', 'req', '-new',
     '-key', '/home/pyuser/certs/client.key',
     '-out', '/home/pyuser/certs/client.csr',
     '-subj', '/CN=lorawan/O=gateway/C=SG'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("CSR:", "OK" if not err or b'error' not in err.lower() else err)

# Step 4 - Sign CSR with internal CA
# CA files must be in /home/pyuser/certs/ for the serial file to be writable
r = subprocess.Popen(
    ['openssl', 'x509', '-req', '-days', '365',
     '-in', '/home/pyuser/certs/client.csr',
     '-CA', '/home/pyuser/certs/ca-mqtt.crt',
     '-CAkey', '/home/pyuser/certs/ca-mqtt.key',
     '-CAcreateserial',
     '-out', '/home/pyuser/certs/client.crt'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("Sign:", err)

# Step 5 - Verify the generated certificate
r = subprocess.Popen(
    ['openssl', 'x509', '-in', '/home/pyuser/certs/client.crt',
     '-noout', '-subject'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("Verify:", out, err)
