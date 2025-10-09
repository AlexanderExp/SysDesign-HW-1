import os

EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")
# кэши/таймауты
TARIFF_TTL_SEC = int(os.getenv("TARIFF_TTL_SEC", "600"))  # 10 мин по тз
CONFIG_REFRESH_SEC = int(os.getenv("CONFIG_REFRESH_SEC", "60"))
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "1.5"))
R_BUYOUT = int(os.getenv("R_BUYOUT", "5000"))  # пример, потом из конфига
