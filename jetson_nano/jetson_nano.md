# JETSON OCCUPANCY MONITOR SETUP

## SETUP

### 1. Start the Occupancy Monitor

Run the occupancy monitoring script:
```bash
python3 occupancy_monitor_rtsp.py
```
### 2. Start Docker Containers

Start the Docker Compose containers:
```bash
docker compose up -d
```
## TROUBLESHOOTING

If the camera is not working, restart the occupancy monitor and Docker containers.

1. Find and Kill Existing Occupancy Monitor Processes
Find Python processes related to occupancy_monitor_rtsp.py:
```bash
ps aux | grep python
```
Identify the relevant PID and terminate the process:
```bash
kill -9 <PID>
```
If there are multiple occupancy_monitor_rtsp.py processes, terminate each relevant process.

2. Restart the Occupancy Monitor
Run:
```bash
python3 occupancy_monitor_rtsp.py
```
3. Restart Docker Containers
Restart the Docker Compose containers:
```bash
docker compose restart
```
