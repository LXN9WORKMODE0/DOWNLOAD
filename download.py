"""Download and verify regional IFS forecasts. Run with --help for entry points."""
import argparse
import calendar
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import eccodes as ec
from ecmwfapi import ECMWFService
from ecmwfapi.api import ANONYMOUS_APIKEY_VALUES, get_apikey_values


HERE = Path(__file__).resolve().parent
CONFIG = json.loads((HERE / "plan.json").read_text(encoding="utf-8-sig"))
CUTOVER = datetime.fromisoformat(CONFIG["first_upgraded_run_utc"])
GROUPS = CONFIG["groups"]
PARTS = {"surface": ("oper", "sfc"), "pressure": ("oper", "pl"), "wave": ("wave", "sfc")}


def package(group, part):
    selected = GROUPS[group]
    names = selected.get(part, [])
    if not names:
        return None
    levels = selected["levels"] if part == "pressure" else []
    return {**{k:v for k,v in CONFIG.items() if k not in ("groups","param_ids","accumulated")},
            "group":group, "area_nwse":selected.get("area_nwse",CONFIG["area_nwse"]),
            "part":part, "stream":PARTS[part][0], "levtype":PARTS[part][1],
            "levels":levels, "parameters":{p:CONFIG["param_ids"][p] for p in names},
            "accumulated_ids":[CONFIG["param_ids"][p] for p in names if p in CONFIG["accumulated"]]}


def horizon(cycle):
    return CONFIG["horizon_before_after_hours"][int(cycle >= CUTOVER)]


def steps(cycle):
    early = CONFIG["early_through_hours"]
    stride = CONFIG["later_step_hours"]
    return list(range(0, early+1, CONFIG["early_step_hours"])) + list(range(early+stride, horizon(cycle)+1, stride))

SIZES = (1, 2, 4, 8)


def save(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")
    tmp.replace(path)


@contextmanager
def writer(root, plan):
    # OS releases the lock on exit, including crashes.
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".writer").open("a+b") as lock:
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        spec = root / "plan.json"
        if spec.exists() and json.loads(spec.read_text(encoding="utf8")) != plan:
            raise ValueError("Configuration differs from stored plan; use a separate --root.")
        if not spec.exists():
            save(spec, plan)
        yield


def check_access(root):
    from urllib.parse import urlsplit
    from urllib.request import getproxies, proxy_bypass
    # The project's .env is an ECMWF Web API JSON key file.
    project_key = HERE / ".env"
    if project_key.is_file():
        os.environ.setdefault("ECMWF_API_RC_FILE", str(project_key))
    endpoint = "https://api.ecmwf.int/v1"
    configured = False
    credential_state = "absent"
    try:
        key, url, email = get_apikey_values()
        configured = (key, url, email) != ANONYMOUS_APIKEY_VALUES and bool(key and email)
        credential_state = "configured" if configured else "absent"
        if configured:
            endpoint = url.rstrip("/")
    except Exception as exc:
        credential_state = type(exc).__name__
    start = time.monotonic()
    reachable = False
    winerror = None
    try:
        with urlopen(endpoint + "/", timeout=10) as response:
            status = response.status
            reachable = True
    except HTTPError as exc:
        status = exc.code
        reachable = 400 <= exc.code < 500 and exc.code not in (407,429)
    except (URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        winerror = getattr(reason, "winerror", None)
        status = str(reason)
    probe_seconds = round(time.monotonic() - start, 3)
    decoder = "ok"
    try:
        handle = ec.codes_grib_new_from_samples("regular_ll_sfc_grib2")
        ec.codes_release(handle)
    except Exception as exc:
        decoder = type(exc).__name__
    remote = urlsplit(endpoint)
    proxy = None if proxy_bypass(remote.hostname) else getproxies().get(remote.scheme)
    proxy_host = urlsplit(proxy).hostname if proxy else None
    network_disabled = os.getenv("CODEX_SANDBOX_NETWORK_DISABLED") == "1"
    report = dict(utc=datetime.now(timezone.utc).isoformat(), host=remote.hostname,
                  credential_state=credential_state, reachable=reachable,
                  winerror=winerror, proxy_host=proxy_host, sandbox_network_disabled=network_disabled,
                  probe_result=status, probe_seconds=probe_seconds, eccodes_sample=decoder)
    save(root / "connection.json", report)
    print(json.dumps(report, ensure_ascii=True), flush=True)
    if not reachable and network_disabled and winerror == 10013:
        raise RuntimeError("This session disables network sockets (WinError 10013). No MARS job submitted.")
    if not configured or not reachable:
        raise RuntimeError("Preflight blocked. See connection.json. No MARS job submitted.")
    if decoder != "ok":
        raise RuntimeError("ecCodes sample could not be opened; check the ecCodes installation and temporary directory.")


def cycles(year):
    return [datetime(year, 1, 1, h) + timedelta(days=d)
            for d in range(365 + calendar.isleap(year)) for h in CONFIG["cycles_utc"]]


def request(batch, plan):
    if horizon(batch[0]) != horizon(batch[-1]):
        raise ValueError("Split at the IFS upgrade before requesting.")
    dates = sorted({d.strftime("%Y%m%d") for d in batch})
    hours = sorted({d.strftime("%H") for d in batch})
    if len(dates) * len(hours) != len(batch):
        raise ValueError("MARS date/time Cartesian product would include extra cycles.")
    return dict(**{"class": "od"}, stream=plan["stream"], type="fc", expver="1", levtype=plan["levtype"],
                **({"levelist": "/".join(map(str,plan["levels"]))} if plan["levels"] else {}),
                date="/".join(dates), time="/".join(hours),
                step="/".join(map(str, steps(batch[0]))), param="/".join(map(str, plan["parameters"].values())),
                area="/".join(map(str, plan["area_nwse"])), grid="/".join([str(plan["grid_degrees"])]*2),
                expect="any")  # Independently check every requested field below.


def validate(path, batch, plan):
    dates = {(int(d.strftime("%Y%m%d")), d.hour * 100): d for d in batch}
    # A bit per field keeps the annual coverage check small even for pressure-level archives.
    indexes = {}
    required = {}
    for limit in {horizon(d) for d in batch}:
        sample = next(d for d in batch if horizon(d) == limit)
        fields = [(s,p,level) for s in steps(sample) for p in plan["parameters"].values()
                  for level in (plan["levels"] or [None])]
        indexes[limit] = {field: 1 << i for i,field in enumerate(fields)}
        required[limit] = sum(bit for (s,p,_),bit in indexes[limit].items() if s or p not in plan["accumulated_ids"])
    masks = dict.fromkeys(dates,0)
    valid_times = {(cycle,lead): (int(v.strftime("%Y%m%d")),v.hour*100)
                   for cycle in batch for lead in steps(cycle) for v in [cycle+timedelta(hours=lead)]}
    north, west, south, east = plan["area_nwse"]
    delta = plan["grid_degrees"]
    grid = (round((east-west)/delta)+1, round((north-south)/delta)+1,
            north, west, south, east, delta, delta)
    count = 0
    with path.open("rb") as src:
        offset = 0
        while (gid := ec.codes_grib_new_from_file(src)) is not None:
            try:
                def get(key):
                    return ec.codes_get(gid, key)
                day, hour, lead, param = map(get, ("dataDate","dataTime","endStep","paramId"))
                ident = day, hour, lead, param
                actual_grid = tuple(map(get, ("Ni","Nj","latitudeOfFirstGridPointInDegrees",
                    "longitudeOfFirstGridPointInDegrees","latitudeOfLastGridPointInDegrees",
                    "longitudeOfLastGridPointInDegrees","iDirectionIncrementInDegrees","jDirectionIncrementInDegrees")))
                if (actual_grid != grid or get("gridType") != "regular_ll" or get("centre") != "ecmf"
                        or get("dataType") != "fc" or str(get("stepUnits")) not in ("1", "h")
                        or get("numberOfPoints") != grid[0]*grid[1]
                        or ec.codes_get_message_offset(gid) != offset):
                    raise ValueError(f"Unexpected grid, product, units or framing at {ident}")
                cycle = dates.get((day,hour))
                if cycle is None:
                    raise ValueError(f"Unexpected initialization {ident}")
                level = get("level") if plan["levels"] else None
                bit = indexes[horizon(cycle)].get((lead,param,level),0)
                is_accum = param in plan["accumulated_ids"]
                if not bit or masks[day,hour] & bit:
                    raise ValueError(f"Unexpected or duplicate field {ident}, level={level}")
                if plan["levels"] and get("typeOfLevel") != "isobaricInhPa":
                    raise ValueError(f"Unexpected level type at {ident}")
                if valid_times.get((cycle,lead)) != (get("validityDate"),get("validityTime")):
                    raise ValueError(f"Incorrect valid time at {ident}")
                kind = get("stepType")
                # Some ECMWF GRIB1 table 128 fields carry only the forecast endpoint.
                # Accept the native encoding; do not infer or rewrite interval metadata.
                endpoint_only = (is_accum and param in (169,175,228) and kind == "instant"
                                 and plan["stream"] == "oper" and get("edition") == 1
                                 and get("table2Version") == 128 and get("startStep") == lead
                                 and get("timeRangeIndicator") in ((0,1,10) if lead == 0 else (0,10)))
                if kind != ("accum" if is_accum else "instant") and not endpoint_only:
                    raise ValueError(f"Unexpected stepType={kind} at {ident}")
                if kind == "accum" and not 0 <= get("startStep") <= lead:
                    raise ValueError(f"Invalid accumulation window {ident}")
                masks[day,hour] |= bit
                count += 1
                offset += ec.codes_get_message_size(gid)
            finally:
                ec.codes_release(gid)
        if offset != path.stat().st_size:
            raise ValueError(f"Unreadable or unexpected bytes at {offset}")
    for key,cycle in dates.items():
        missing = required[horizon(cycle)] & ~masks[key]
        if missing:
            first = next(f for f,b in indexes[horizon(cycle)].items() if missing & b)
            raise ValueError(f"{key}: {missing.bit_count()} missing fields; first (step,param,level): {first}")
    return count


def tag(batch):
    return batch[0].strftime("%Y%m%d%H") + "_" + batch[-1].strftime("%Y%m%d%H")


def archive_cost(root, batch, plan):
    # LIST only takes archive selection keys; area/grid are retrieval post-processing.
    selection = {k:v for k,v in request(batch,plan).items() if k not in ("grid","area","expect")}
    mars = "list, output=cost, " + ", ".join(f"{k}={v}" for k,v in selection.items())
    directory = root / str(batch[0].year) / "cost"
    directory.mkdir(parents=True,exist_ok=True)
    path = directory / (tag(batch) + ".txt")
    tmp = path.with_suffix(".part")
    start = time.monotonic()
    ECMWFService("mars",log=lambda msg: None).execute(mars,str(tmp))
    raw = tmp.read_text(encoding="utf8")
    keys = re.findall(r"(?m)^\s*(\w+)\s*=\s*(\d+)\s*;",raw)
    values = {k:int(v) for k,v in keys}
    if len(values) != len(keys) or not {"number_of_tapes","number_of_fields"} <= values.keys():
        raise ValueError(f"Missing or ambiguous MARS cost; inspect {tmp}")
    per_cycle = len(steps(batch[0]))*len(plan["parameters"])
    nlevels = len(plan["levels"]) or 1
    maximum = per_cycle * nlevels * len(batch)
    minimum = maximum - len(plan["accumulated_ids"])*nlevels*len(batch)
    values["field_count_ok"] = minimum <= values["number_of_fields"] <= maximum
    values["list_s"] = round(time.monotonic()-start,3)
    values["batch"] = tag(batch)
    tmp.replace(path)
    with (root/"costs.jsonl").open("a",encoding="utf8") as log:
        log.write(json.dumps(values)+"\n")
    return values


def select_batch(root, candidates, plan):
    """Compare nested selections to the exact first run, using fresh catalogue costs."""
    sizes = [n for n in reversed(SIZES) if n <= len(candidates)]
    costs = {}
    def probe(n):
        if n not in costs:
            costs[n] = archive_cost(root,candidates[:n],plan)
        return costs[n]
    width = sizes[0]
    largest = probe(width)
    if largest["field_count_ok"] and largest["number_of_tapes"] == 0:
        # Every field of this selection, including its first run, is online.
        baseline = 0
    else:
        base = probe(1)
        baseline = base["number_of_tapes"]
        if not base["field_count_ok"] or baseline > 1:
            raise ValueError(f"Single run exceeds one tape or lacks fields: {base}")
        for width in sizes:
            candidate = probe(width)
            if candidate["field_count_ok"] and candidate["number_of_tapes"] <= baseline:
                break
    accepted = costs[width]
    return candidates[:width], dict(tapes=accepted["number_of_tapes"],baseline_tapes=baseline,
            baseline_queried=1 in costs,tape_files=accepted.get("number_of_tape_files"),
            listed_fields=accepted["number_of_fields"],list_calls=len(costs),
            list_s=round(sum(v["list_s"] for v in costs.values()),3))


def fetch(root, batch, plan, cost, trial=None):
    folder = root / str(batch[0].year) / ("tape_pilot_chunks" if trial else "chunks")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (tag(batch) + ".grib")
    if target.exists():
        validate(target, batch, plan)
        return target
    tmp = target.with_suffix(".part")
    start = time.monotonic()
    events = {}
    row = dict(trial=trial, archive_cost=cost, batch=tag(batch), cycles=len(batch), utc=datetime.now(timezone.utc).isoformat())

    def log(msg):
        if msg == "Request submitted" or msg.startswith("Request is "):
            events.setdefault(msg, time.monotonic())
            print(msg, flush=True)
        elif msg.startswith(("Transfering ", "Transferring ")):
            events.setdefault("transfer", time.monotonic())
        elif msg.startswith("Transfer rate "):
            events["last_transfer_end"] = time.monotonic()
        elif msg.startswith("Request id: "):
            row["request_id"] = msg.split(": ", 1)[1]
    try:
        ECMWFService("mars", log=log).execute(request(batch, plan), str(tmp))
        done = time.monotonic()
        row["bytes"] = tmp.stat().st_size
        transfer = events.get("transfer")
        submitted = events.get("Request submitted")
        active = events.get("Request is active")
        completed = events.get("Request is complete")
        if submitted and completed:
            row["to_ready_s"] = round(completed-submitted,3)
        if submitted and transfer:
            row["archive_wait_and_service_s"] = round(transfer-submitted, 3)
        if submitted and active:
            row["webapi_wait_to_active_s"] = round(active-submitted, 3)
        if active and transfer:
            row["active_to_transfer_s"] = round(transfer-active, 3)
        if transfer and "last_transfer_end" in events:
            row["transfer_s"] = round(events["last_transfer_end"]-transfer, 3)
        row["retrieve_s"] = round(done-start, 3)
        row["phase"] = "validation"
        row["fields"] = validate(tmp, batch, plan)
        tmp.replace(target)
        row["phase"] = "verified"
        row["ok"] = True
    except Exception as exc:
        row.update(ok=False, error_type=type(exc).__name__)
        raise
    finally:
        row["wall_s"] = round(time.monotonic()-start, 3)
        with (root / "timings.jsonl").open("a", encoding="utf8") as f:
            f.write(json.dumps(row) + "\n")
        print(json.dumps(row), flush=True)
    return target


def benchmark(root, year, plan):
    # Use distinct useful data for the control and expanded orders; alternate order across regimes.
    for month, modes in [(2, ("single","expanded")), (12, ("expanded","single"))]:
        for mode in modes:
            trial = ["tape_cost",year,month,mode]
            rows = read_timings(root)
            previous = next((r for r in reversed(rows) if r["trial"]==trial),None)
            if previous:
                dates = [datetime.strptime(v,"%Y%m%d%H") for v in previous["batch"].split("_")]
                batch = [d for d in cycles(year) if dates[0]<=d<=dates[1]]
                cached = root/str(year)/"tape_pilot_chunks"/(previous["batch"]+".grib")
                partial = cached.with_suffix(".part")
                if previous["ok"] and cached.exists():
                    validate(cached,batch,plan)
                    continue
                if not previous["ok"] and (previous.get("phase") == "validation" or previous.get("error_type") == "ValueError") and (cached.exists() or partial.exists()):
                    saved = cached if cached.exists() else partial
                    start = time.monotonic()
                    fields = validate(saved,batch,plan)
                    if saved == partial:
                        partial.rename(cached)
                    record_recovery(root,previous,cached,fields,time.monotonic()-start,"ecCodes")
                    continue
            day = 1 if mode=="single" else 3
            begin = datetime(year,month,day)
            candidates = [begin + timedelta(hours=12*k) for k in range(1 if mode=="single" else max(SIZES))]
            batch,cost = select_batch(root,candidates,plan)
            fetch(root,batch,plan,cost,trial=trial)
    return summarize(root,year)


def read_timings(root):
    path = root/"timings.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()] if path.exists() else []


def record_recovery(root, previous, path, fields, validation_s, decoder):
    row = {k:v for k,v in previous.items() if k != "error_type"}
    row.update(ok=True,phase="verified",recovered=True,fields=fields,bytes=path.stat().st_size,
               recovery_decoder=decoder,revalidation_s=round(validation_s,3),
               wall_s=round(previous["wall_s"]+validation_s,3))
    with (root/"timings.jsonl").open("a",encoding="utf8") as out:
        out.write(json.dumps(row)+"\n")


def summarize(root, year):
    rows = [r for r in read_timings(root) if r["ok"] and r["trial"] and r["trial"][:2]==["tape_cost",year]]
    observations = []
    for r in rows:
        cost = r["archive_cost"]
        n = r["cycles"]
        observations.append(dict(month=r["trial"][2],mode=r["trial"][3],cycles=n,tapes=cost["tapes"],
            baseline_tapes=cost["baseline_tapes"],list_calls=cost["list_calls"],list_s=cost["list_s"],
            wait_to_active_s=r.get("webapi_wait_to_active_s"),archive_wait_and_service_s=r.get("archive_wait_and_service_s"),
            transfer_s=r.get("transfer_s"),bytes=r["bytes"],fields=r["fields"],
            seconds_per_cycle=round((cost["list_s"]+r["wall_s"])/n,3)))
    comparisons = []
    for month in (2,12):
        pair = {r["mode"]:r for r in observations if r["month"]==month}
        if pair.keys() != {"single","expanded"}:
            continue
        a,b = pair["single"],pair["expanded"]
        comparable = b["cycles"]>1 and a["tapes"]==b["tapes"]
        wait_gain = None
        if comparable and a["wait_to_active_s"] is not None and b["wait_to_active_s"] is not None:
            wait_gain = round(a["wait_to_active_s"] - b["wait_to_active_s"]/b["cycles"],3)
        comparisons.append(dict(month=month,matched_tape_count=comparable,
            observed_wait_s_saved_per_cycle=wait_gain,observed_total_s_saved_per_cycle=
            round(a["seconds_per_cycle"]-b["seconds_per_cycle"],3) if comparable else None))
    result = dict(year=year,observations=observations,comparisons=comparisons)
    save(root/f"tape_pilot_{year}.json",result)
    print(json.dumps(result),flush=True)
    return result


def annual(root, year, width, plan):
    timeline = cycles(year)
    folder = root / str(year)
    folder.mkdir(exist_ok=True)
    target = folder / f"{plan['group']}_{plan['part']}_{year}.grib"
    if target.exists():
        count = validate(target, timeline, plan)
    else:
        # Reuse validated benchmark chunks and any previous partially completed annual run.
        chunks = [p for sub in ("chunks","benchmark_chunks","tape_pilot_chunks") for p in (folder / sub).glob("*.grib")]
        starts = {}
        for p in chunks:
            first, last = [datetime.strptime(s,"%Y%m%d%H") for s in p.stem.split("_")]
            if first not in starts or last > starts[first][0]:
                starts[first] = (last,p)
        i = 0
        ordered = []
        while i < len(timeline):
            first = timeline[i]
            if first in starts:
                last, path = starts[first]
                end_index = timeline.index(last)+1
                validate(path,timeline[i:end_index],plan)
                ordered.append(path)
            else:
                end_index = min(i+width,len(timeline))
                end_index = next((j for j in range(i+1,end_index) if timeline[j] in starts or horizon(timeline[j]) != horizon(first)),end_index)
                # Any multi-date request uses both configured daily cycles.
                if first.hour != 0:
                    end_index = i+1
                elif end_index-i > 1 and (end_index-i)%2:
                    end_index -= 1
                batch,cost = select_batch(root,timeline[i:end_index],plan)
                end_index = i+len(batch)
                ordered.append(fetch(root,batch,plan,cost))
            i = end_index
        need = sum(p.stat().st_size for p in ordered)
        if shutil.disk_usage(folder).free < need:
            raise OSError("Insufficient free space for annual merge; verified chunks retained.")
        tmp = target.with_suffix(".part")
        with tmp.open("wb") as dst:
            for p in ordered:
                with p.open("rb") as src:
                    shutil.copyfileobj(src,dst,4*1024*1024)
        count = validate(tmp,timeline,plan)
        tmp.replace(target)
    save(folder / "verified.json", dict(year=year, cycles=len(timeline), fields=count,
         bytes=target.stat().st_size, file=target.name, validation="GRIB headers, coverage, grid and windows"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check","plan","benchmark","report","year"])
    parser.add_argument("--year", type=int, default=2024, choices=CONFIG["years"])
    parser.add_argument("--root", type=Path, default=HERE / "output")
    parser.add_argument("--batch", type=int, choices=SIZES, help="explicit cycles per production request")
    parser.add_argument("--group",choices=[*GROUPS,"all"],default="hydrodynamics")
    args = parser.parse_args()
    groups = list(GROUPS) if args.group=="all" else [args.group]
    for group in groups:
        run_group(args,group)


def run_group(args, group):
    for part in PARTS:
        plan = package(group,part)
        if plan is None:
            continue
        # Keep the previous seven-day output and all incompatible runs separate.
        root = args.root / "full_range" / group / part
        if group == "shipping":
            root = root / "global"
        if args.action == "plan":
            timeline = cycles(args.year)
            for limit in dict.fromkeys(map(horizon,timeline)):
                eligible = [d for d in timeline if horizon(d)==limit]
                width = args.batch or 1
                # Display an aligned example plus the exact coverage interval.
                start = next((i for i,d in enumerate(eligible) if d.hour==0),0) if width>1 else 0
                print(json.dumps(dict(group=group,part=part,first_utc=eligible[0].isoformat(),
                    last_utc=eligible[-1].isoformat(),cycles=len(eligible),
                    request=request(eligible[start:start+width],plan)),indent=2))
            continue
        with writer(root,plan):
            if args.action == "report":
                summarize(root,args.year)
                continue
            check_access(root)
            if args.action == "benchmark":
                benchmark(root,args.year,plan)
            elif args.action == "year":
                annual(root,args.year,args.batch or max(SIZES),plan)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        sys.exit(str(exc))
