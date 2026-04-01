from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AntiBotResult:
    detected: bool
    anti_bot_type: str | None = None
    details: str | None = None


_PATTERNS = [
    (r"cf-browser-verification|cf-challenge|cloudflare", "cloudflare"),
    (r"g-recaptcha|recaptcha/api", "recaptcha"),
    (r"datadome\.co|dd\.js", "datadome"),
    (r"fingerprint2|fingerprintjs|fp\.min\.js", "fingerprint"),
    (r"challenge-platform|hcaptcha", "custom_js"),
]


def detect_anti_bot(html: str) -> AntiBotResult:
    html_lower = html.lower()
    for pattern, bot_type in _PATTERNS:
        if re.search(pattern, html_lower):
            return AntiBotResult(
                detected=True,
                anti_bot_type=bot_type,
                details=f"Detected {bot_type} pattern",
            )
    return AntiBotResult(detected=False)


STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-accelerated-2d-canvas",
    "--no-first-run",
    "--no-zygote",
    "--disable-gpu",
]

STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
