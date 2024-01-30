import os


class Config:
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
    LOGGING_CONFIG_FILE = os.path.join(BASE_DIR, 'logging.ini')

config = Config()