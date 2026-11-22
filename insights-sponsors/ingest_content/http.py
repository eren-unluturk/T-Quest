"""Polite single-threaded JSON fetcher: User-Agent naming the project, delay between requests,
backoff on errors, raw responses cached on disk so reruns are resumable and cheap."""
import hashlib
import json
import time
from pathlib import Path

import httpx

USER_AGENT = "T-Quest-Hackathon/1.0"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
DELAY_S = 1.0


class Fetcher:
    def __init__(self, source: str, delay: float = DELAY_S, raw_dir: Path = RAW_DIR):
        self.dir = raw_dir / source
        self.dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.network_calls = 0
        self.client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60, follow_redirects=True)

    def get_json(self, url: str, params: dict | None = None):
        key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
        cache = self.dir / f"{key}.json"
        if cache.exists():
            return json.loads(cache.read_text(encoding="utf-8"))
        last = None
        for attempt in range(4):
            time.sleep(self.delay * (2**attempt) if attempt else self.delay)
            self.network_calls += 1
            try:
                r = self.client.get(url, params=params)
                if r.status_code in (429, 500, 502, 503, 504):
                    last = f"HTTP {r.status_code}"
                    continue
                r.raise_for_status()
                data = r.json()
                cache.write_text(json.dumps(data), encoding="utf-8")
                return data
            except (httpx.HTTPError, ValueError) as e:
                last = type(e).__name__
        raise RuntimeError(f"giving up on {url.split('?')[0]}: {last}")
