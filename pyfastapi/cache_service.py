import json
import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class CacheConfig:
    backend: str
    ttl_seconds: int
    max_entries: int
    lat_lng_precision: int
    tz_precision: int
    key_prefix: str
    redis_url: Optional[str]

    @staticmethod
    def from_env() -> "CacheConfig":
        return CacheConfig(
            backend=os.getenv("CACHE_BACKEND", "memory").strip().lower(),
            ttl_seconds=max(1, int(os.getenv("CACHE_TTL_SECONDS", "900"))),
            max_entries=max(1, int(os.getenv("CACHE_MAX_ENTRIES", "1024"))),
            lat_lng_precision=max(0, int(os.getenv("CACHE_LAT_LNG_PRECISION", "2"))),
            tz_precision=max(0, int(os.getenv("CACHE_TZ_PRECISION", "2"))),
            key_prefix=os.getenv("CACHE_KEY_PREFIX", "horoscope:v1"),
            redis_url=os.getenv("REDIS_URL"),
        )


class CacheMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._writes = 0
        self._errors = 0

    def hit(self):
        with self._lock:
            self._hits += 1

    def miss(self):
        with self._lock:
            self._misses += 1

    def write(self):
        with self._lock:
            self._writes += 1

    def error(self):
        with self._lock:
            self._errors += 1

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "writes": self._writes,
                "errors": self._errors,
                "requests": total,
                "hit_rate": round(hit_rate, 6),
            }


class BaseCacheBackend:
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        raise NotImplementedError


class InMemoryTTLCache(BaseCacheBackend):
    def __init__(self, max_entries: int):
        self._max_entries = max_entries
        self._store: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()

    def _evict_expired(self, now: float) -> None:
        expired_keys = [key for key, (expires_at, _) in self._store.items() if expires_at <= now]
        for key in expired_keys:
            self._store.pop(key, None)

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            record = self._store.get(key)
            if record is None:
                return None
            expires_at, payload = record
            if expires_at <= now:
                self._store.pop(key, None)
                return None
            self._store.move_to_end(key)
            return payload

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        now = time.time()
        with self._lock:
            self._evict_expired(now)
            self._store[key] = (now + ttl_seconds, value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)


class RedisCacheBackend(BaseCacheBackend):
    def __init__(self, redis_url: str):
        import redis  # type: ignore

        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self._redis.ping())

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        cached = self._redis.get(key)
        if cached is None:
            return None
        return json.loads(cached)

    def set(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        self._redis.setex(key, ttl_seconds, json.dumps(value))


class HoroscopeCacheService:
    def __init__(self, config: CacheConfig):
        self.config = config
        self.metrics = CacheMetrics()
        self.backend_name = "memory"
        self._backend = self._build_backend(config)
        self._log_startup_backend_status()

    @staticmethod
    def _build_backend(config: CacheConfig) -> BaseCacheBackend:
        if config.backend not in {"memory", "redis"}:
            logger.warning("cache_backend_select backend=%s status=invalid fallback=memory", config.backend)
            return InMemoryTTLCache(config.max_entries)

        if config.backend == "redis":
            redis_url = config.redis_url
            if not redis_url:
                raise RuntimeError("CACHE_BACKEND=redis requires REDIS_URL")
            return RedisCacheBackend(redis_url)

        return InMemoryTTLCache(config.max_entries)

    def _log_startup_backend_status(self) -> None:
        requested_backend = self.config.backend
        if isinstance(self._backend, RedisCacheBackend):
            self.backend_name = "redis"
            try:
                self._backend.ping()
                logger.info("cache_backend_startup requested=%s selected=redis redis_ping=ok", requested_backend)
            except Exception as redis_error:
                logger.error(
                    "cache_backend_startup requested=%s selected=redis redis_ping=error error=%s",
                    requested_backend,
                    redis_error,
                )
                raise RuntimeError("Redis cache backend connectivity check failed") from redis_error
            return

        self.backend_name = "memory"
        logger.info(
            "cache_backend_startup requested=%s selected=memory reason=%s",
            requested_backend,
            "local_or_dev" if requested_backend == "memory" else "fallback_or_invalid",
        )

    def normalize_key_fields(
        self,
        *,
        dob: str,
        time_value: str,
        lat: float,
        lng: float,
        tz: float,
        language: str,
    ) -> Dict[str, Any]:
        return {
            "dob": dob.strip(),
            "time": time_value.strip(),
            "lat": round(lat, self.config.lat_lng_precision),
            "lng": round(lng, self.config.lat_lng_precision),
            "tz": round(tz, self.config.tz_precision),
            "language": language.strip().lower(),
        }

    def build_cache_key(self, normalized_fields: Dict[str, Any]) -> str:
        normalized_json = json.dumps(normalized_fields, sort_keys=True, separators=(",", ":"))
        return f"{self.config.key_prefix}:{normalized_json}"

    @staticmethod
    def _obfuscated_key(cache_key: str) -> str:
        key_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()[:12]
        key_prefix = cache_key.split(":", 1)[0]
        return f"{key_prefix}:{key_hash}"

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        safe_key = self._obfuscated_key(cache_key)
        try:
            cached = self._backend.get(cache_key)
            if cached is None:
                self.metrics.miss()
                logger.debug("cache_lookup status=miss backend=%s key=%s", self.backend_name, safe_key)
                return None
            self.metrics.hit()
            logger.debug("cache_lookup status=hit backend=%s key=%s", self.backend_name, safe_key)
            return cached
        except Exception as cache_error:
            self.metrics.error()
            logger.warning("cache_lookup status=error key=%s error=%s", safe_key, cache_error)
            return None

    def set(self, cache_key: str, payload: Dict[str, Any]) -> None:
        safe_key = self._obfuscated_key(cache_key)
        try:
            self._backend.set(cache_key, payload, self.config.ttl_seconds)
            self.metrics.write()
            logger.debug(
                "cache_store status=ok backend=%s ttl=%s key=%s",
                self.backend_name,
                self.config.ttl_seconds,
                safe_key,
            )
        except Exception as cache_error:
            self.metrics.error()
            logger.warning("cache_store status=error key=%s error=%s", safe_key, cache_error)
