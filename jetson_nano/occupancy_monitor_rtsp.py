# Occupancy Monitoring program with RTSP streaming
import cv2
import torch
from ultralytics import YOLO
import time
import subprocess
import os
from datetime import datetime
import csv
import json
from collections import deque
from statistics import median

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("⚠️ paho-mqtt not installed. MQTT features disabled.")


# --- Configuration ---
# Camera Settings
USE_CSI_CAMERA = True
CAMERA_SOURCE = 0
FLIP_METHOD = 0

# Detection Settings
CONFIDENCE_THRESHOLD = 0.45
MODEL_NAME = "yolov8n.pt"
ENABLE_OCCUPANCY_SMOOTHING = True
SMOOTHING_WINDOW_SIZE = 7

# RTSP Streaming Settings
ENABLE_RTSP_STREAM = True
RTSP_URL = "rtsps://localhost:8332/occupancy"
STREAM_WIDTH = 1280
STREAM_HEIGHT = 720
STREAM_FPS = 10

FORCE_HEADLESS = True

# Logging Settings
ENABLE_LOGGING = True
LOG_FILE = "occupancy_log.csv"
LOG_INTERVAL = 30  # Heartbeat interval in seconds (set to 0 to disable heartbeat)

# MQTT Settings
ENABLE_MQTT = True
MQTT_BROKER = "192.168.0.105"
MQTT_PORT = 8883
MQTT_TOPIC = "occupancy/monitor"
MQTT_CLIENT_ID = "jetson_occupancy_monitor"
MQTT_QOS = 1
MQTT_PUBLISH_INTERVAL_SECONDS = 60  # Publish occupancy every 60s (set to 0 to publish every frame)

# Recovery Settings
CAMERA_RECOVERY_ATTEMPTS = 5
CAMERA_RECOVERY_DELAY_SECONDS = 2
RTSP_RECOVERY_ATTEMPTS = 3
RTSP_RECOVERY_DELAY_SECONDS = 2


def get_csi_pipeline(
    sensor_id=0,
    capture_width=1280,
    capture_height=720,
    display_width=1280,
    display_height=720,
    framerate=30,
    flip_method=0,
):
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, "
        f"format=(string)NV12, framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink drop=1"
    )


def create_rtsp_stream(use_hardware=True):
    if use_hardware:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{STREAM_WIDTH}x{STREAM_HEIGHT}",
            "-r",
            str(STREAM_FPS),
            "-i",
            "-",
            "-c:v",
            "h264_nvenc",
            "-preset",
            "llhp",
            "-tune",
            "ull",
            "-zerolatency",
            "1",
            "-b:v",
            "2M",
            "-maxrate",
            "2M",
            "-bufsize",
            "1M",
            "-g",
            str(STREAM_FPS),
            "-f",
            "rtsp",
            "-rtsp_transport",
            "tcp",
            RTSP_URL,
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{STREAM_WIDTH}x{STREAM_HEIGHT}",
            "-r",
            str(STREAM_FPS),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-tune",
            "zerolatency",
            "-b:v",
            "2M",
            "-maxrate",
            "2M",
            "-bufsize",
            "1M",
            "-g",
            str(STREAM_FPS),
            "-f",
            "rtsp",
            "-rtsp_transport",
            "tcp",
            RTSP_URL,
        ]

    return subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )


def setup_mqtt_client():
    if not (ENABLE_MQTT and MQTT_AVAILABLE):
        return None

    try:
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)
        client.tls_set(ca_certs="/home/jetsonorin/Desktop/certs/ca.crt", certfile="/home/jetsonorin/Desktop/certs/jetson.crt", keyfile="/home/jetsonorin/Desktop/certs/jetson.key")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        print(f"✅ MQTT connected: {MQTT_BROKER}:{MQTT_PORT}")
        return client
    except Exception as error:
        print(f"⚠️ Failed to setup MQTT: {error}")
        print("   Continuing without MQTT...")
        return None


def should_publish_mqtt(last_publish_time, now_ts):
    if MQTT_PUBLISH_INTERVAL_SECONDS <= 0:
        return True
    return (now_ts - last_publish_time) >= MQTT_PUBLISH_INTERVAL_SECONDS


def open_camera():
    if USE_CSI_CAMERA:
        print("📷 Opening Raspberry Pi Camera (CSI/GStreamer)...")
        pipeline = get_csi_pipeline(flip_method=FLIP_METHOD)
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    else:
        print(f"📷 Opening USB Camera (Source {CAMERA_SOURCE})...")
        cap = cv2.VideoCapture(CAMERA_SOURCE, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc("M", "J", "P", "G"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

    return cap


def start_rtsp_stream_with_fallback():
    print(f"📡 Starting RTSP stream to {RTSP_URL}...")
    rtsp_process = create_rtsp_stream(use_hardware=True)
    time.sleep(2)
    if rtsp_process.poll() is not None:
        print("⚠️ Hardware encoder failed. Falling back to software encoder...")
        rtsp_process = create_rtsp_stream(use_hardware=False)
        time.sleep(1)
    return rtsp_process


def restart_rtsp_stream(current_process):
    if current_process:
        try:
            current_process.stdin.close()
        except Exception:
            pass
        try:
            current_process.terminate()
        except Exception:
            pass

    for attempt in range(1, RTSP_RECOVERY_ATTEMPTS + 1):
        print(
            f"🔄 Attempting RTSP recovery ({attempt}/{RTSP_RECOVERY_ATTEMPTS}) in {RTSP_RECOVERY_DELAY_SECONDS}s..."
        )
        time.sleep(RTSP_RECOVERY_DELAY_SECONDS)
        try:
            rtsp_process = start_rtsp_stream_with_fallback()
            if rtsp_process and rtsp_process.poll() is None:
                print("✅ RTSP recovery successful. Resuming stream.")
                return rtsp_process
        except Exception as error:
            print(f"⚠️ RTSP recovery attempt failed: {error}")

    print("❌ RTSP recovery failed. Disabling RTSP streaming.")
    return None


def main():
    preview_enabled = (not FORCE_HEADLESS) and bool(os.environ.get("DISPLAY"))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"🚀 Starting Occupancy Monitor using device: {device.upper()}")
    if device == "cpu":
        print("⚠️ WARNING: Running on CPU. Performance may be slow.")
    if preview_enabled:
        print("🖥️ Preview window enabled")
    else:
        print("🖥️ Running in headless mode (no local preview window)")

    print(f"📥 Loading YOLO model: {MODEL_NAME}...")
    try:
        model = YOLO(MODEL_NAME)
        model.to(device)
    except Exception as error:
        print(f"❌ Error loading model: {error}")
        return

    cap = open_camera()

    if not cap.isOpened():
        print("❌ Failed to open camera! Check connection.")
        return

    print("✅ Camera opened successfully. Press 'q' to quit.")

    rtsp_process = None
    if ENABLE_RTSP_STREAM:
        try:
            rtsp_process = start_rtsp_stream_with_fallback()
            print("✅ RTSP streaming enabled")
        except Exception as error:
            print(f"⚠️ Failed to start RTSP stream: {error}")
            print("   Continuing without streaming...")
            rtsp_process = None

    mqtt_client = setup_mqtt_client()

    log_file = None
    csv_writer = None
    last_logged_count = -1
    last_log_time = 0

    if ENABLE_LOGGING:
        try:
            file_exists = os.path.isfile(LOG_FILE)
            log_file = open(LOG_FILE, "a", newline="")
            csv_writer = csv.writer(log_file)
            if not file_exists:
                csv_writer.writerow(["Timestamp", "Occupancy", "FPS"])
                log_file.flush()
            print(f"📝 Logging enabled: {LOG_FILE}")
        except Exception as error:
            print(f"⚠️ Failed to open log file: {error}")
            print("   Continuing without logging...")

    prev_time = 0
    last_mqtt_publish_time = 0
    recent_counts = deque(maxlen=max(1, SMOOTHING_WINDOW_SIZE))

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Failed to grab frame. Camera might be disconnected or busy.")
                recovered = False
                for attempt in range(1, CAMERA_RECOVERY_ATTEMPTS + 1):
                    print(
                        f"🔄 Attempting camera recovery ({attempt}/{CAMERA_RECOVERY_ATTEMPTS}) in {CAMERA_RECOVERY_DELAY_SECONDS}s..."
                    )
                    time.sleep(CAMERA_RECOVERY_DELAY_SECONDS)

                    try:
                        cap.release()
                    except Exception:
                        pass

                    cap = open_camera()
                    if cap.isOpened():
                        print("✅ Camera recovery successful. Resuming stream.")
                        recovered = True
                        break

                if recovered:
                    continue

                print("❌ Camera recovery failed. Stopping monitor.")
                break

            results = model(frame, conf=CONFIDENCE_THRESHOLD, classes=[0], verbose=False)
            num_people_raw = len(results[0].boxes)

            if ENABLE_OCCUPANCY_SMOOTHING:
                recent_counts.append(num_people_raw)
                num_people = int(median(recent_counts))
            else:
                num_people = num_people_raw

            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time

            if ENABLE_LOGGING and csv_writer:
                occupancy_changed = num_people != last_logged_count
                heartbeat_due = LOG_INTERVAL > 0 and (curr_time - last_log_time) >= LOG_INTERVAL
                should_log = occupancy_changed or heartbeat_due

                if should_log:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    csv_writer.writerow([timestamp, num_people, f"{fps:.1f}"])
                    log_file.flush()
                    last_logged_count = num_people
                    last_log_time = curr_time

            if mqtt_client and should_publish_mqtt(last_mqtt_publish_time, curr_time):
                try:
                    payload = json.dumps(
                        {
                            "occupancy": num_people,
                            "timestamp": datetime.now().isoformat(),
                            "fps": round(fps, 1),
                        }
                    )
                    mqtt_client.publish(MQTT_TOPIC, payload, qos=MQTT_QOS)
                    last_mqtt_publish_time = curr_time
                except Exception as error:
                    print(f"⚠️ MQTT publish error: {error}")

            annotated_frame = results[0].plot()
            _, width = annotated_frame.shape[:2]
            cv2.rectangle(annotated_frame, (0, 0), (width, 60), (0, 0, 0), -1)

            color = (0, 255, 0) if num_people < 5 else (0, 0, 255)
            cv2.putText(
                annotated_frame,
                f"Occupancy: {num_people}",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                color,
                2,
            )
            cv2.putText(
                annotated_frame,
                f"FPS: {fps:.1f}",
                (width - 150, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )

            if ENABLE_RTSP_STREAM and rtsp_process:
                cv2.circle(annotated_frame, (width - 30, 30), 8, (0, 0, 255), -1)
                cv2.putText(
                    annotated_frame,
                    "LIVE",
                    (width - 70, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 0, 255),
                    1,
                )

            if ENABLE_RTSP_STREAM and rtsp_process:
                try:
                    if rtsp_process.poll() is not None:
                        print("⚠️ RTSP process exited unexpectedly.")
                        rtsp_process = restart_rtsp_stream(rtsp_process)
                        if not rtsp_process:
                            continue

                    stream_frame = cv2.resize(annotated_frame, (STREAM_WIDTH, STREAM_HEIGHT))
                    rtsp_process.stdin.write(stream_frame.tobytes())
                except (BrokenPipeError, OSError):
                    print("⚠️ RTSP pipe closed.")
                    rtsp_process = restart_rtsp_stream(rtsp_process)
                except Exception as error:
                    print(f"⚠️ RTSP streaming error: {error}")

            if preview_enabled:
                cv2.imshow("Jetson Occupancy Monitor", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    except KeyboardInterrupt:
        print("\n🛑 Stopping...")

    finally:
        cap.release()
        cv2.destroyAllWindows()

        if rtsp_process:
            try:
                rtsp_process.stdin.close()
            except Exception:
                pass
            rtsp_process.wait(timeout=2)
            print("✅ RTSP stream closed")

        if mqtt_client:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
            print("✅ MQTT disconnected")

        if log_file:
            log_file.close()
            print("✅ Log file closed")

        print("🛑 Program stopped.")


if __name__ == "__main__":
    main()
