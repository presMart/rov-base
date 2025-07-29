import json, pathlib
from pydantic import BaseModel
from typing import List


class DepthSensorConfig(BaseModel):
    adc_channel: int
    voltage_range: List[float]
    pressure_range_psi: List[float]
    atmospheric_psi: float


class Settings(BaseModel):
    trusted_clients: list[str] = ["10.0.0.", "127.0.0.1", "192.168.8."]
    motor_channels: dict[str, dict[str, int | str]]
    motor_smoothing_factor: float = 0.8
    input_poll_rate_hz: int = 100
    estop_duration: float = 2.0
    gamepad_deadzone: float = 0.1
    gamepad_thrust_steps: list[float] = [0.25, 0.5, 0.75, 1.0]
    boost_buttons: list[int] = [10, 11]
    burst_thrust_val: float = 0.75
    pwm_min: int = 1100
    pwm_neutral: int = 1500
    pwm_max: int = 1900
    pwm_freq: int = 50
    voltage_warning: float
    voltage_limited: float
    voltage_critical: float
    depth_sensor: DepthSensorConfig
    telemetry_host: str = "192.168.1.225"
    host: str = "0.0.0.0"
    port: int = 9000
    camera_device_index: int = 0
    camera_resolution: tuple[int, int] = (640, 480)
    camera_fps: int = 30
    camera_stream_url: str = "http://rov.local:8000/stream.mjpg"
    log_file_path: str = "rov_log.txt"
    logging_max_lines: int = 500
    heartbeat_interval: int = 30
    telemetry_poll_rate_ms: int = 200
    dht_sensor_map: dict[str, dict[str, int | str]]


def load_config(path="config.json") -> Settings:
    raw = json.loads(pathlib.Path(path).read_text())
    return Settings(**raw)
    