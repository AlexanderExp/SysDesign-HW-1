# services/rental-core/app/config_cache.py
import os
import sys
import time
import threading
from typing import Any, Dict, Optional
from threading import RLock, Event

from .clients import get_configs, set_config, refresh_configs
from .model import ConfigMap

# период фонового обновления
_REFRESH_SEC = int(os.getenv("CONFIG_REFRESH_SEC", "60"))

# локальный снапшот (для get_config / get_all)
_state_lock = RLock()
_state: Optional[ConfigMap] = None

# управление фоновым потоком
_worker: Optional[threading.Thread] = None
_stop_event: Optional[Event] = None


def load_initial_or_die(max_wait_sec: int = 30) -> bool:
    """Пробуем подтянуть конфиги с ретраями, чтобы не падать на гонке старта."""
    deadline = time.monotonic() + max_wait_sec
    last_err = None
    while time.monotonic() < deadline:
        try:
            cfg = get_configs()      # clients.py сам дернёт /configs и закеширует
            # гарантируем, что clients увидит актуальные конфиги
            set_config(cfg)
            with _state_lock:        # обновим локальный снапшот для get_config/get_all
                global _state
                _state = cfg
            print("[startup] configs loaded", file=sys.stderr, flush=True)
            return True
        except Exception as e:
            last_err = e
            time.sleep(1.0)
    print(f"[startup] configs NOT loaded after {max_wait_sec}s: {last_err}",
          file=sys.stderr, flush=True)
    return False


def _refresh_once() -> bool:
    """Один проход обновления конфигов снаружи и локального снапшота."""
    try:
        cfg = refresh_configs()      # ходит наружу и вызывает set_config внутри clients.py
        with _state_lock:
            global _state
            _state = cfg
        return True
    except Exception as e:
        # допускаем бесконечное использование старых данных
        print(
            f"[config_cache] refresh failed: {e}", file=sys.stderr, flush=True)
        return False


def background_refresh() -> None:
    """
    Сохранено ради обратной совместимости (если кто-то напрямую вызывает).
    Бесконечный цикл обновления с соном _REFRESH_SEC.
    """
    while True:
        _refresh_once()
        time.sleep(_REFRESH_SEC)


def start_configs_refresher(*_args, **_kwargs) -> None:
    """
    Новый API, который ждёт main.py — запускает фоновой поток.
    Подпись допускает лишние аргументы (например, app), чтобы не падать.
    """
    global _worker, _stop_event
    if _worker and _worker.is_alive():
        return
    _stop_event = Event()

    def _loop():
        # первый проход сразу (без задержки) — затем с периодом
        _refresh_once()
        while not _stop_event.is_set():
            # ждём период; если нас просят остановиться — выходим
            if _stop_event.wait(_REFRESH_SEC):
                break
            _refresh_once()

    _worker = threading.Thread(
        target=_loop, name="configs-refresher", daemon=True
    )
    _worker.start()
    print("[config_cache] refresher started", file=sys.stderr, flush=True)


def stop_configs_refresher(*_args, **_kwargs) -> None:
    """Аккуратная остановка фонового потока (можно вызвать из shutdown-хука)."""
    global _worker, _stop_event
    if _stop_event:
        _stop_event.set()
    if _worker:
        _worker.join(timeout=2.0)
    _worker = None
    _stop_event = None
    print("[config_cache] refresher stopped", file=sys.stderr, flush=True)


def get_config(key: str, default=None):
    with _state_lock:
        if _state is None:
            raise RuntimeError("config not initialized")
        data = _state._data if hasattr(_state, "_data") else {}
        return data.get(key, default)


def get_all() -> Dict[str, Any]:
    with _state_lock:
        if _state is None:
            raise RuntimeError("config not initialized")
        return dict(_state._data)
