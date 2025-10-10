import os

# базовый URL внешних заглушек (stations/tariffs/users/configs/payments)
EXTERNAL_BASE = os.getenv("EXTERNAL_BASE", "http://external-stubs:3629")

# HTTP
HTTP_TIMEOUT_SEC = float(os.getenv("HTTP_TIMEOUT_SEC", "1.5"))

# tariffs cache
TARIFF_TTL_SEC = int(os.getenv("TARIFF_TTL_SEC", "600")
                     )  # 10 минут по умолчанию

# Redis (для офферов)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
OFFER_TTL_SEC = int(os.getenv("OFFER_TTL_SEC", "60")
                    )  # контроль свежести оффера

# ценообразование
MAGIC_LOW_BANKS = int(os.getenv("MAGIC_LOW_BANKS", "2"))  # порог «мало банок»
# fallback если нет конфигов
LAST_BANKS_INCREASE = float(os.getenv("LAST_BANKS_INCREASE", "1.5"))
# множитель при фоллбэке users
GREEDY_PRICE_MULT = float(os.getenv("GREEDY_PRICE_MULT", "1.2"))
FREE_PERIOD_MIN_SUBSCRIBER = int(
    os.getenv("FREE_PERIOD_MIN_SUBSCRIBER", "30"))  # минимум для подписчиков
