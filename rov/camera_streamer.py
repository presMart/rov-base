"""
camera_streamer.py

Provides an HTTP MJPEG streaming server using the PiCamera2 library for live
video from the ROV. Streams frames as JPEGs via /stream.mjpg for browser or
GUI client consumption. Supports configurable resolution and framerate.
"""

import io
import threading
import time
from http import server
from picamera2 import Picamera2
from PIL import Image
import logging
from config import load_config

# Configure logging
log = logging.getLogger(__name__)

cfg = load_config()

# HTML landing page for root access to server
PAGE = """\
<html>
<head><title>ROV Camera</title></head>
<body><h1>ROV Live Feed</h1>
<img src="/stream.mjpg" width="640" height="480">
</body>
</html>
"""


class StreamingOutput:
    """
    Thread-safe buffer for the most recent JPEG frame, to be shared between
    the capture loop and HTTP handler. Notifies waiting clients on new frame.
    """

    def __init__(self):
        self.frame = None
        self.condition = threading.Condition()

    def update_frame(self, new_frame):
        """
        Update buffer with new JPEG frame and notify all waiting clients.

        Args:
            new_frame (bytes): JPEG-encoded image data.
        """
        with self.condition:
            self.frame = new_frame
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    """
    Handles HTTP GET requests for both the landing page and MJPEG video stream.
    Streams multipart JPEG frames to clients at /stream.mjpg.
    """

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(PAGE.encode("utf-8"))

        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header("Age", 0)
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=FRAME"
            )
            self.end_headers()

            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b"--FRAME\r\n")
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
            except Exception as e:
                log.error(f"Client disconnected: {self.client_address} — {e}")

        else:
            self.send_error(404)
            self.end_headers()


def capture_loop(camera, output, stop_event, framerate=24):
    """
    Capture loop: continuously grabs frames from the PiCamera,
    converts them to JPEG, and updates the output buffer for streaming.

    Args:
        camera (Picamera2): Camera instance.
        output (StreamingOutput): Shared frame buffer.
        stop_event (threading.Event): Allows clean thread shutdown.
        framerate (int): Desired frames per second.
    """
    interval = 1.0 / framerate
    frame_count = 0

    while not stop_event.is_set():
        try:
            frame = camera.capture_array("main")
            if frame is None:
                log.warning("[CameraStreamer] Frame capture returned None.")
                continue

            jpeg_bytes = io.BytesIO()
            try:
                Image.fromarray(frame).save(jpeg_bytes, format="JPEG", quality=85)
                output.update_frame(jpeg_bytes.getvalue())
            except Exception as e:
                log.warning(f"[CameraStreamer] Failed to convert frame to JPEG: {e}")
                continue

            frame_count += 1
            if frame_count % 24 == 0:
                log.debug(
                    f"[CameraStreamer] Frame: {frame_count}, time: {time.monotonic():.2f}"
                )

        except Exception as e:
            log.error(f"[CameraStreamer] Frame capture failed: {e}")

        stop_event.wait(timeout=interval)


def start_streaming_server(port=8000, resolution=(640, 480), framerate=24):
    """
    Start the camera capture thread and HTTP MJPEG server.

    Args:
        port (int): TCP port to bind the HTTP server.
        resolution (tuple): (width, height) for video stream.
        framerate (int): Frames per second for capture/stream.
    """
    global output
    output = StreamingOutput()
    stop_event = threading.Event()

    log.info("Initializing camera...")
    picam = Picamera2()
    cam_config = picam.create_video_configuration(
        main={"size": resolution, "format": "BGR888"}, controls={"FrameRate": framerate}
    )
    log.info(f"Camera configuration: {cam_config}")
    picam.configure(cam_config)
    picam.start()
    log.info("Camera started.")

    threading.Thread(
        target=capture_loop, args=(picam, output, stop_event, framerate), daemon=True
    ).start()

    server_address = ("", port)
    server_instance = server.HTTPServer(server_address, StreamingHandler)
    log.info(f"Streaming server started on port {port}.")

    try:
        server_instance.serve_forever()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received. Stopping camera stream...")
        stop_event.set()
        server_instance.shutdown()


if __name__ == "__main__":
    start_streaming_server()
