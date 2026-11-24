"""Resolve shared storage aliases and register verified annual outputs."""
import argparse
import calendar
import csv
import json
from pathlib import Path, PurePosixPath, PureWindowsPath


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "catalog" / "assets.csv"
LOCATIONS = ROOT / ".local" / "locations.json"
CLIENTS = ROOT / "catalog" / "research" / "clients"


def local_path(paths, storage, relative):
    if not paths.get(storage):
        return None
    rel = PurePosixPath(relative)
    if rel.is_absolute() or PureWindowsPath(relative).drive or "\\" in relative or ".." in rel.parts:
        raise ValueError(f"Invalid relative path: {relative}")
    base = Path(paths[storage]).expanduser()
    if not base.is_absolute():
        raise ValueError(f"Use an absolute local root for {storage}")
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError(f"Path outside storage root: {relative}")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("validate", help="check shared research catalog references offline")
    locate = commands.add_parser("locate")
    locate.add_argument("--task")
    locate.add_argument("--client", choices=sorted(path.stem for path in CLIENTS.glob("*.json")))
    register = commands.add_parser("register-year")
    register.add_argument("group")
    register.add_argument("year", type=int)
    register.add_argument("storage", help="alias for the DataRoot used by download.py")
    args = parser.parse_args()
    if args.action == "validate":
        from catalog_validation import validate_catalog

        try:
            print(validate_catalog(ROOT))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            parser.exit(1, f"Invalid catalog: {exc}\n")
        return
    paths = json.loads(LOCATIONS.read_text(encoding="utf-8-sig")) if LOCATIONS.exists() else {}
    with ASSETS.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns, rows = reader.fieldnames, list(reader)
    if args.action == "locate":
        if args.client:
            client = json.loads((CLIENTS / f"{args.client}.json").read_text(encoding="utf-8"))
            rows = [{
                **asset,
                "task_id": asset.get("task_id", asset["dataset"]),
                "bytes": asset.get("bytes"),
            } for asset in client["assets"]]
        for row in rows:
            if args.task and row["task_id"] != args.task:
                continue
            path = local_path(paths, row["storage_id"], row["relative_path"])
            state = "unmapped" if path is None else "missing"
            if path is not None and path.exists():
                state = "present"
                if row["bytes"] and path.stat().st_size != int(row["bytes"]):
                    state = "size-mismatch"
            print(f"{row['task_id']}  {state}  {row['storage_id']}  {path or row['relative_path']}")
        return

    plan = json.loads((ROOT / "plan.json").read_text(encoding="utf-8-sig"))
    if args.group not in plan["groups"] or args.year not in plan["years"]:
        parser.error("Unknown group or year in plan.json")
    fields = plan["groups"][args.group]
    expected_cycles = (365 + calendar.isleap(args.year)) * len(plan["cycles_utc"])
    task = f"{args.group}-{args.year}"
    updates = {}
    for part in ("surface", "pressure", "wave"):
        if part not in fields:
            continue
        directory = PurePosixPath("full_range", args.group, part)
        if args.group == "shipping":
            directory /= "global"
        directory /= str(args.year)
        name = f"{args.group}_{part}_{args.year}.grib"
        relative = (directory / name).as_posix()
        path = local_path(paths, args.storage, relative)
        if path is None:
            parser.error(f"Map {args.storage} in .local/locations.json first")
        receipt = json.loads(path.with_name("verified.json").read_text(encoding="utf-8-sig"))
        if (receipt["year"] != args.year or receipt["cycles"] != expected_cycles
                or receipt["file"] != name or receipt["fields"] <= 0
                or not path.is_file() or path.stat().st_size != receipt["bytes"] or receipt["bytes"] <= 0):
            raise ValueError(f"Annual file and verification receipt disagree: {relative}")
        updates[relative] = dict(task_id=task, storage_id=args.storage, relative_path=relative,
                                 status="annual_verified", bytes=receipt["bytes"], fields=receipt["fields"],
                                 cycles=expected_cycles, scope=f"{args.year} UTC initializations")
    rows = [r for r in rows if (r["storage_id"] != args.storage or r["relative_path"] not in updates)]
    tmp = ASSETS.with_suffix(".csv.tmp")
    with tmp.open("w",encoding="utf8",newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows + list(updates.values()))
    tmp.replace(ASSETS)
    print(f"Registered {len(updates)} annual product(s) for {task} at {args.storage}")


if __name__ == "__main__":
    main()
