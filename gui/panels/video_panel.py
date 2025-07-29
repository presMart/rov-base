"""
video_panel.py

Implements the VideoPanel for displaying the ROV's live camera feed.
Uses a dedicated worker thread (MJPEGStreamWorker) to robustly decode
MJPEG-over-HTTP video streams, supporting reconnection and GUI-thread safety.

Why not use OpenCV VideoCapture? This custom parser provides better reliability
and cross-platform performance for streaming MJPEG, avoiding known OpenCV
network/timeout bugs.
"""

import requests
import cv2
import numpy as np
from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QLabel
import threading
import time


class MJPEGStreamWorker(QObject):
    """
    Worker thread for robust MJPEG-over-HTTP video streaming.

    - Reads MJPEG byte stream, extracts JPEG frames, decodes them with OpenCV,
        and emits new frames via Qt signal.
    - Automatically attempts to reconnect on error or stream drop.
    - Designed for GUI-thread safety and to avoid blocking the main event loop.
    """

    new_frame = pyqtSignal(np.ndarray)
    _worker_thread: threading.Thread | None

    def __init__(self, stream_url):
        """
        Args:
            stream_url (str): URL of the MJPEG stream to read.
        """
        super().__init__()
        self.stream_url = stream_url
        self.running = False
        self._worker_thread = None

    def start(self):
        """Start the background thread for grabbing video frames."""
        if self.running:
            return
        self.running = True
        self._worker_thread = threading.Thread(target=self.grab_loop, daemon=True)
        self._worker_thread.start()

    def grab_loop(self):
        """
        Main thread loop for reading and decoding MJPEG frames.

        Attempts reconnection on error. Never blocks the GUI.
        """
        while self.running:
            try:
                with requests.get(self.stream_url, stream=True, timeout=10) as r:
                    byte_buffer = b""
                    for chunk in r.iter_content(chunk_size=4096):
                        if not self.running:
                            break
                        byte_buffer += chunk
                        # Extract complete JPEG frames from the byte buffer
                        while True:
                            # JPEG start and end markers
                            start = byte_buffer.find(b"\xff\xd8")
                            end = byte_buffer.find(b"\xff\xd9")
                            if start != -1 and end != -1 and end > start:
                                jpg = byte_buffer[start: end + 2]
                                byte_buffer = byte_buffer[end + 2:]
                                np_arr = np.frombuffer(jpg, dtype=np.uint8)
                                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                                if frame is not None:
                                    self.new_frame.emit(frame)
                            else:
                                break
            except Exception as e:
                print(f"[MJPEGStreamWorker] Stream error: {e}. Reconnecting in 2s...")
                time.sleep(2)

    def stop(self):
        """Stop the worker thread and release resources."""
        self.running = False
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2)


class VideoPanel(QLabel):
    """
    GUI panel for displaying MJPEG camera frames from the ROV.

    - Receives frames from MJPEGStreamWorker in a thread-safe manner.
    - Converts OpenCV images to QPixmap for fast display.
    - Allows resolution and stream URL to be set at creation.
    - Handles resource cleanup on panel close.
    """

    def __init__(
        self,
        stream_url: str,
        parent=None,
        camera_resolution: tuple[int, int] = (640, 480),
    ):
        """
        Args:
            stream_url (str): MJPEG stream URL.
            parent (QWidget, optional): Parent widget.
            camera_resolution (tuple): (width, height) for display.
        """
        super().__init__(parent)
        self.camera_resolution = camera_resolution
        self.setFixedSize(self.camera_resolution[0], self.camera_resolution[1])
        self.setScaledContents(True)

        self.worker = MJPEGStreamWorker(stream_url)
        self.worker.new_frame.connect(self.on_new_frame)
        self.worker.start()

    def on_new_frame(self, frame):
        """
        Qt slot for handling new frames from the worker thread.

        Args:
            frame (np.ndarray): Decoded OpenCV image.
        """
        try:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            img = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            self.setPixmap(QPixmap.fromImage(img))
        except Exception as e:
            print(f"[VideoPanel] Failed to update frame: {e}")

    def stop(self):
        """Stop the MJPEG worker thread and clean up resources."""
        self.worker.stop()

    def closeEvent(self, a0):
        """Handle panel close event to stop the worker thread."""
        self.stop()
        super().closeEvent(a0)
