"""A polite HTTP client for collecting the old website: one request at a time, a pause between requests,
a normal browser user agent, two retries, and a hard cap on the total number of requests."""

import time
import urllib.error
import urllib.request

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
PAUSE = 1.0  # seconds between requests
RETRIES = 2  # retries after the first attempt
BUDGET = 100  # about the most requests this task may make in total


class Client:
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.last = 0.0

    def used(self) -> int:
        try:
            with open(self.log_path, encoding="utf-8") as f:
                return sum(1 for _ in f)
        except FileNotFoundError:
            return 0

    def _log(self, url: str, status: str) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(f"{status}\t{url}\n")

    def get(self, url: str) -> tuple[int | None, bytes, str | None, str]:
        """Returns (http status or None, body, content type, error text). Never raises."""
        err = ""
        for attempt in range(RETRIES + 1):
            if self.used() >= BUDGET:
                return None, b"", None, "request budget used up"
            wait = PAUSE - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read()
                    self._log(url, str(r.status))
                    return r.status, body, r.headers.get("Content-Type"), ""
            except urllib.error.HTTPError as e:
                self._log(url, str(e.code))
                err = f"HTTP {e.code}"
                if e.code in (404, 410):  # retrying will not help
                    return e.code, b"", None, err
            except Exception as e:  # network trouble, timeouts
                self._log(url, "ERR")
                err = f"{type(e).__name__}: {e}"
            time.sleep(2)
        return None, b"", None, err
