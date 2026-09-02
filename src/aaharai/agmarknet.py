from __future__ import annotations

import csv
import json
import urllib.parse
from datetime import date, datetime
from pathlib import Path

from .http import get_json
from .open_sources import PUBLIC_DATA_GOV_KEY
from .paths import PROCESSED, RAW
from .provenance import append_event, sha256_file, utc_now


RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
EXPECTED_FIELDS = {
    "state",
    "district",
    "market",
    "commodity",
    "variety",
    "grade",
    "arrival_date",
    "min_price",
    "max_price",
    "modal_price",
}


def _url(offset: int, limit: int, state: str | None = None) -> str:
    parameters: dict[str, str | int] = {
        "api-key": PUBLIC_DATA_GOV_KEY,
        "format": "json",
        "offset": offset,
        "limit": limit,
    }
    if state is not None:
        # The API applies OR token matching to multi-word filter values. Every
        # reporting state in this snapshot has a unique first token; returned rows
        # are still verified against the complete expected state name below.
        parameters["filters[state]"] = state.split()[0]
    return f"https://api.data.gov.in/resource/{RESOURCE_ID}?{urllib.parse.urlencode(parameters)}"


def _state_partitions(overview: dict) -> list[str]:
    """Use exact state spellings exposed by the API's largest valid result window.

    Completeness is not assumed from this list: the caller rejects the snapshot unless
    the sum of all resulting state partitions equals the separately reported global total.
    """
    return sorted({record["state"] for record in overview.get("records", [])})


def fetch_snapshot(force: bool = False, page_size: int = 10_000) -> Path:
    """Fetch the complete current API snapshot without assuming absent rows are zero."""
    run_date = date.today().isoformat()
    destination = RAW / "agmarknet" / f"agmarknet_snapshot_{run_date}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        return destination

    records: list[dict] = []
    total = None
    metadata = None
    try:
        overview = get_json(_url(0, 10_000))
        if overview.get("status") != "ok":
            raise RuntimeError(f"AGMARKNET overview API status was {overview.get('status')!r}")
        total = int(overview["total"])
        metadata = {k: v for k, v in overview.items() if k != "records"}
        partition_counts: dict[str, int] = {}
        partitions = _state_partitions(overview)
        if not partitions:
            raise RuntimeError("AGMARKNET overview returned no state names")
        for state in partitions:
            state_records: list[dict] = []
            offset = 0
            partition_total: int | None = None
            while partition_total is None or offset < partition_total:
                payload = get_json(_url(offset, page_size, state))
                if payload.get("status") != "ok":
                    raise RuntimeError(
                        f"AGMARKNET state partition {state!r} at offset {offset} "
                        f"returned status {payload.get('status')!r}"
                    )
                page = payload.get("records", [])
                unexpected_states = {record.get("state") for record in page} - {state}
                if unexpected_states:
                    raise RuntimeError(
                        f"AGMARKNET filter for {state!r} returned other states: {sorted(unexpected_states)}"
                    )
                partition_total = int(payload.get("total", len(page)))
                state_records.extend(page)
                if not page:
                    break
                offset += len(page)
            if len(state_records) != partition_total:
                raise RuntimeError(
                    f"Incomplete AGMARKNET state partition {state!r}: "
                    f"received {len(state_records)} of {partition_total}"
                )
            partition_counts[state] = partition_total
            records.extend(state_records)
        if len(records) != total:
            raise RuntimeError(
                f"AGMARKNET state partitions summed to {len(records)} rows but the global API total is {total}"
            )
        actual_fields = set(records[0]) if records else set()
        if actual_fields != EXPECTED_FIELDS:
            raise ValueError(
                f"AGMARKNET schema changed. Expected {sorted(EXPECTED_FIELDS)}, got {sorted(actual_fields)}"
            )
        payload_out = {
            "fetched_at": utc_now(),
            "source_url": _url(0, page_size),
            "metadata": metadata,
            "partition_strategy": "exact source state-name filters",
            "partition_counts": partition_counts,
            "records": records,
        }
        temp = destination.with_suffix(".tmp")
        temp.write_text(json.dumps(payload_out, ensure_ascii=False), encoding="utf-8")
        temp.replace(destination)
        append_event(
            {
                "source_id": "agmarknet_daily",
                "status": "acquired",
                "action": "api_snapshot",
                "path": str(destination),
                "records": len(records),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )
        return destination
    except Exception as exc:
        append_event(
            {
                "source_id": "agmarknet_daily",
                "status": "failed",
                "action": "api_snapshot",
                "path": str(destination),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        raise


def normalize_snapshot(path: Path) -> Path:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["records"]
    output = PROCESSED / "agmarknet_daily_prices.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "snapshot_date",
        "arrival_date",
        "state_name_source",
        "district_name_source",
        "market_name",
        "commodity_name_source",
        "variety_name_source",
        "commercial_grade",
        "min_price_inr_per_quintal",
        "max_price_inr_per_quintal",
        "modal_price_inr_per_quintal",
        "source_id",
        "source_artifact",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            parsed_date = datetime.strptime(row["arrival_date"], "%d/%m/%Y").date().isoformat()
            writer.writerow(
                {
                    "snapshot_date": path.stem.rsplit("_", 1)[-1],
                    "arrival_date": parsed_date,
                    "state_name_source": row["state"],
                    "district_name_source": row["district"],
                    "market_name": row["market"],
                    "commodity_name_source": row["commodity"],
                    "variety_name_source": row["variety"],
                    "commercial_grade": row["grade"],
                    "min_price_inr_per_quintal": row["min_price"],
                    "max_price_inr_per_quintal": row["max_price"],
                    "modal_price_inr_per_quintal": row["modal_price"],
                    "source_id": "agmarknet_daily",
                    "source_artifact": str(path),
                }
            )
    return output
