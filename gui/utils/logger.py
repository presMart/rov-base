import logging
from logging.handlers import RotatingFileHandler
from PyQt6.QtCore import QObject, pyqtSignal
import os


def get_logger(
    name: str, level=logging.INFO, log_to_file=False, log_dir="logs"
) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.hasHandlers():
        return logger

    logger.setLevel(level)

    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    if log_to_file:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            f"{log_dir}/{name}.log", maxBytes=500_000, backupCount=3
        )
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


class GuiLogEmitter(QObject):
    log_signal = pyqtSignal(str)


class GuiLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.emitter = GuiLogEmitter()

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.emitter.log_signal.emit(msg)


class GuiLoggerAdapter:
    def __init__(self, gui_panel=None, fallback=None):
        self.gui_panel = gui_panel
        self.fallback = fallback or print  # fallback to print if GUI not present

    def log(self, message: str):
        if self.gui_panel:
            self.gui_panel.append_log(message)
        else:
            self.fallback(message)

    def append_log(self, message: str):  # compatibility with legacy usage
        self.log(message)
