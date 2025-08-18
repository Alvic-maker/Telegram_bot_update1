
import time
_cache = {}
def set_cache(key, value, ttl=60):
    _cache[key] = (value, time.time()+ttl)
def get_cache(key):
    v = _cache.get(key)
    if not v: return None
    val, exp = v
    if time.time() > exp:
        del _cache[key]; return None
    return val
