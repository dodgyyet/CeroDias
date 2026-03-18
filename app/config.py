# Platform difficulty mode:
#   0 = Easy   — SECRET_KEY is static and guessable; session forgery is a one-step SSTI chain
#   1 = Medium — SECRET_KEY is runtime-generated; session forgery path is closed
#   2 = Hard   — (reserved) additional surface hardening, more steps required per chain
# TODO: read DIFFICULTY from a config file (e.g. ctf_config.json) rather than hardcoding here,
#       so operators can change the mode without touching Python. Then conditionally set SECRET_KEY:
#       DIFFICULTY == 0 → SECRET_KEY = 'flask-2b7f3a9c8d1e4f6a'
#       DIFFICULTY >= 1 → SECRET_KEY = os.urandom(24)  (generated at startup, not recoverable via SSTI)
DIFFICULTY = 0


class Config:
    SECRET_KEY = 'flask-2b7f3a9c8d1e4f6a'
    DEBUG = True
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True
    SEED_MODE = True
    TIME_PENALTY_PER_MINUTE = 1
    ENABLED_VULNERABILITIES = ['sql_injection']
    DIFFICULTY_LEVELS = ['Easy', 'Medium']


class TestingConfig(Config):
    TESTING = True
    SEED_MODE = True
