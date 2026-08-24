from __future__ import annotations

import json
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any


USER_AGENT = "AaharAI-data/0.1 (+research reproducibility)"


def _run_curl(arguments: list[str], *, timeout: int = 120) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "--retry",
            "5",
            "--retry-delay",
            "2",
            "--retry-max-time",
            "60",
            "--retry-all-errors",
            "--user-agent",
            USER_AGENT,
            *arguments,
        ],
        check=True,
        capture_output=True,
    )


def get_json(url: str, *, timeout: int = 120) -> Any:
    return json.loads(_run_curl([url], timeout=timeout).stdout)


def post_form_json(url: str, values: dict[str, str | int], *, timeout: int = 120) -> Any:
    encoded = urllib.parse.urlencode(values)
    result = _run_curl(
        ["--header", "Content-Type: application/x-www-form-urlencoded", "--data", encoded, url],
        timeout=timeout,
    )
    return json.loads(result.stdout)


def download_to(url: str, destination: Path, *, timeout: int = 120) -> dict[str, str | int]:
    result = _run_curl(
        [
            "--output",
            str(destination),
            "--write-out",
            "%{http_code}\t%{content_type}",
            url,
        ],
        timeout=timeout,
    )
    status, _, content_type = result.stdout.decode("utf-8").partition("\t")
    return {"http_status": int(status), "content_type": content_type, "client": "curl_verified_tls"}
