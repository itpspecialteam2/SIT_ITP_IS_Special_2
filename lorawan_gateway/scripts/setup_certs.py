# setup_certs.py
# Run this script FIRST before any other scripts.
#
# What this does:
#   Creates the persistent certificate directory /home/pyuser/certs/
#   on the gateway's eMMC storage. This directory survives reboots
#   unlike /tmp which is cleared on every reboot.
#
# How to run:
#   1. SSH into the gateway
#   2. en
#   3. config t
#   4. python
#   5. debug setup_certs.py
#
# Expected output:
#   mkdir: OK
#   write test: OK
#   Done: /home/pyuser/certs

import subprocess

# Create the persistent certs directory
r = subprocess.Popen(
    ['mkdir', '-p', '/home/pyuser/certs'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("mkdir:", err if err else "OK")

# Verify it is writable
r = subprocess.Popen(
    ['touch', '/home/pyuser/certs/test.txt'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
out, err = r.communicate()
print("write test:", err if err else "OK")

# Clean up test file
subprocess.Popen(
    ['rm', '/home/pyuser/certs/test.txt'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
).communicate()

print("Done: /home/pyuser/certs")
