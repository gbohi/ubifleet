"""Cache des permissions — clé = (role_id, module, action)"""

import time
import threading

_cache: dict = {}
_cache_time: float = 0
_lock = threading.Lock()
CACHE_TTL = 300  # 5 minutes


def _load_from_db() -> dict:
    from apps.accounts.models import PermissionRole
    cache = {}
    for perm in PermissionRole.objects.select_related('role').all():
        key = (str(perm.role_id), perm.module, perm.action)
        cache[key] = perm.autorise
    return cache


def get_cache() -> dict:
    global _cache, _cache_time
    now = time.time()
    if now - _cache_time > CACHE_TTL:
        with _lock:
            if now - _cache_time > CACHE_TTL:
                try:
                    _cache = _load_from_db()
                    _cache_time = now
                except Exception:
                    pass
    return _cache


def invalidate():
    global _cache_time
    _cache_time = 0


def is_allowed(role_id, module: str, action: str):
    """None si pas de règle, True/False si règle trouvée."""
    cache = get_cache()
    return cache.get((str(role_id), module, action))
