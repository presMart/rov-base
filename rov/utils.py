import logging


def setup_logging():
    logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
    return logging.getLogger("ROV")


def scale(value, in_min, in_max, out_min, out_max):
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
