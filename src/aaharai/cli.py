from __future__ import annotations

import argparse
import json
import sys

from . import agmarknet, hces, nfhs6, retention
from .mobile_catalog import build_mobile_catalog
from .open_sources import fetch_lgd, fetch_reference_files
from .paths import RAW, ensure_directories
from .validate import run_validation
from .warehouse import build_warehouse


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def fetch_open(force: bool = False) -> None:
    ensure_directories()
    results = []
    results.extend(fetch_reference_files(force=force))
    results.extend(fetch_lgd(force=force))
    results.extend({"path": str(path), "status": "acquired"} for path in nfhs6.fetch_compendiums(force=force))
    market_path = agmarknet.fetch_snapshot(force=force)
    results.append({"path": str(market_path), "status": "acquired"})
    _print(results)


def build() -> None:
    ensure_directories()
    outputs = []
    outputs.append(str(nfhs6.extract_all()))
    snapshots = sorted((RAW / "agmarknet").glob("agmarknet_snapshot_*.json"))
    if not snapshots:
        raise FileNotFoundError("No AGMARKNET snapshot found. Run fetch-open first.")
    outputs.append(str(agmarknet.normalize_snapshot(snapshots[-1])))

    # Imports are local to keep optional extractors isolated.
    from .geography import build_geography
    from .ifct import extract_ifct

    outputs.extend(str(path) for path in build_geography())
    outputs.extend(str(path) for path in extract_ifct())
    outputs.append(str(retention.extract_usda_retention()))
    outputs.append(str(hces.extract_layout()))
    if hces._find_csv_archive() is not None:
        outputs.extend(str(path) for path in hces.import_vegetables())
    warehouse, counts = build_warehouse()
    _print({"outputs": outputs, "warehouse": str(warehouse), "warehouse_rows": counts})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aaharai")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-open", help="Acquire all openly accessible official sources")
    fetch.add_argument("--force", action="store_true")
    sub.add_parser("build", help="Normalize acquired sources and build the warehouse")
    sub.add_parser("validate", help="Run data and access-state checks")
    sub.add_parser("inspect-hces", help="Inspect user-supplied HCES public-use archives")
    sub.add_parser(
        "build-mobile-catalog",
        help="Build a local research-only IFCT mobile-format catalog (not bundled in the app)",
    )

    args = parser.parse_args(argv)
    try:
        if args.command == "fetch-open":
            fetch_open(force=args.force)
        elif args.command == "build":
            build()
        elif args.command == "validate":
            _print(run_validation())
        elif args.command == "inspect-hces":
            _print(hces.inspect_inbox())
        elif args.command == "build-mobile-catalog":
            catalog, manifest = build_mobile_catalog(copy_to_android=True)
            _print({"catalog": str(catalog), "manifest": str(manifest)})
        return 0
    except Exception as exc:
        print(f"ERROR [{type(exc).__name__}]: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
