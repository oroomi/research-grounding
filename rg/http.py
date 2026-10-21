"""Tiny HTTP layer: one fetch function (requests if installed, urllib otherwise), a disk cache
for raw JSON responses, and retry with backoff for 429/5xx.

Everything network goes through `fetch`, so tests replace that one function with a fixture.
Secrets (API keys, the mailto address) are never part of a cache key and never written to disk.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:  # optional, nicer connection reuse; the kit works without it
    import requests as _requests
except Exception:  # pragma: no cover
    _requests = None

USER_AGENT = "research-grounding/0.1 (+https://github.com/oroomi/research-grounding)"
SECRET_PARAMS = {"api_key", "mailto", "key"}


class RateLimited(Exception):
    """The server kept answering 429 after all retries."""


class HttpError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"HTTP {status}: {body[:200]}")
        self.status = status
        self.body = body


def fetch(url: str, headers: dict | None = None, timeout: float = 30.0) -> tuple[int, dict, str]:
    """GET `url`. Returns (status, lower-cased headers, body text). Never raises on HTTP status."""
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    h.update(headers or {})
    if _requests is not None:
        r = _requests.get(url, headers=h, timeout=timeout)
        return r.status_code, {k.lower(): v for k, v in r.headers.items()}, r.text
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read().decode("utf-8", "replace")


def build_url(base: str, params: dict) -> str:
    return base + "?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def cache_key(base: str, params: dict) -> str:
    """Stable key from the request without any secret parameter."""
    clean = {k: v for k, v in sorted(params.items()) if k not in SECRET_PARAMS}
    return hashlib.sha256(json.dumps([base, clean], sort_keys=True).encode()).hexdigest()[:24]


class Cache:
    def __init__(self, directory: str | os.PathLike | None, ttl_days: float = 14.0, refresh: bool = False):
        self.dir = Path(directory) if directory else None
        self.ttl = ttl_days * 86400
        self.refresh = refresh
        if self.dir:
            self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str):
        if not self.dir or self.refresh:
            return None
        p = self.dir / f"{key}.json"
        try:
            if time.time() - p.stat().st_mtime > self.ttl:
                return None
            return json.loads(p.read_text())["data"]
        except (OSError, ValueError, KeyError):
            return None

    def put(self, key: str, data, meta: dict | None = None):
        if not self.dir:
            return
        p = self.dir / f"{key}.json"
        p.write_text(json.dumps({"meta": meta or {}, "data": data}, ensure_ascii=False))


def get_json(base: str, params: dict, *, headers: dict | None = None, cache: Cache | None = None,
             source: str = "", max_retries: int = 4, backoff: float = 2.0, backoff_cap: float = 40.0,
             min_interval: float = 0.0, max_wait: float = 60.0, sleep=None, log=lambda m: None):
    """GET base?params as JSON with disk cache and exponential backoff on 429/5xx.

    Returns (data, from_cache, response_headers). Raises RateLimited / HttpError.
    """
    sleep = sleep or (lambda s: time.sleep(s))  # resolved at call time so tests can patch time.sleep
    key = cache_key(base, params)
    if cache is not None:
        hit = cache.get(key)
        if hit is not None:
            return hit, True, {}
    url = build_url(base, params)
    attempt = 0
    while True:
        if min_interval:
            sleep(min_interval)
        status, hdrs, body = fetch(url, headers)
        if status == 200:
            try:
                data = json.loads(body)
            except ValueError as e:
                raise HttpError(200, f"not JSON: {e}")
            if cache is not None:
                cache.put(key, data, {"source": source, "t": int(time.time())})
            return data, False, hdrs
        if status in (429, 500, 502, 503, 504) and attempt < max_retries:
            ra = hdrs.get("retry-after", "")
            wait = float(ra) if ra.replace(".", "", 1).isdigit() else min(backoff_cap, backoff * (2 ** attempt))
            if wait > max_wait:  # "come back in 4 hours" means the daily budget is gone; do not sit here
                raise RateLimited(f"{source or base}: HTTP {status}, server asks to wait {wait:.0f}s (daily budget used up?)")
            wait = min(backoff_cap, wait) + random.uniform(0, 0.5)
            log(f"{source or 'http'}: HTTP {status}, retry {attempt + 1}/{max_retries} in {wait:.1f}s")
            sleep(wait)
            attempt += 1
            continue
        if status == 429:
            raise RateLimited(f"{source or base}: still 429 after {max_retries} retries")
        raise HttpError(status, body)


def post_json(url: str, headers: dict, payload: dict, timeout: float = 90.0) -> tuple[int, dict]:
    """POST JSON, return (status, parsed JSON body or {})."""
    body = json.dumps(payload).encode()
    h = {"User-Agent": USER_AGENT, "Content-Type": "application/json", "Accept": "application/json"}
    h.update(headers)
    if _requests is not None:
        r = _requests.post(url, data=body, headers=h, timeout=timeout)
        status, text = r.status_code, r.text
    else:
        req = urllib.request.Request(url, data=body, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status, text = resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
    try:
        return status, json.loads(text)
    except ValueError:
        return status, {}
