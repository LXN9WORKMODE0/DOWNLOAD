"""Check the shared research records without reading data volumes or submitting jobs."""
import json
from pathlib import PurePosixPath, PureWindowsPath


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except ValueError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def index_by_id(rows, label):
    result = {}
    for row in rows:
        key = row["id"]
        if not isinstance(key, str) or not key.strip() or key in result:
            raise ValueError(f"{label}: empty or duplicate id {key!r}")
        result[key] = row
    return result


def reference(key, collection, label):
    if key not in collection:
        raise ValueError(f"{label}: unknown reference {key!r}")


def validate_catalog(root):
    catalog = root / "catalog"
    research = catalog / "research"
    index = read_json(research / "index.json")
    projects = index_by_id(index["projects"], "projects")
    datasets = index_by_id(index["datasets"], "datasets")
    stores = read_json(catalog / "locations.example.json")
    workflows = {line[3:].strip() for line in
                 (root / "docs/data-sources.md").read_text(encoding="utf-8").splitlines()
                 if line.startswith("## ")}
    for project, record in projects.items():
        for dataset in record["datasets"]:
            reference(dataset, datasets, project)
    for dataset, record in datasets.items():
        reference(record["workflow"], workflows, dataset)

    tasks = {}
    assets = []
    for path in sorted((research / "clients").glob("*.json")):
        client = read_json(path)
        if client["client"] != path.stem:
            raise ValueError(f"{path.name}: client must match filename")
        assets.extend((path.name, row) for row in client["assets"])
        for key, task in index_by_id(client["tasks"], path.name).items():
            if task["client"] != path.stem or key in tasks:
                raise ValueError(f"{path.name}: conflicting owner for {key}")
            reference(task["project"], projects, key)
            reference(task["workflow"], workflows, key)
            items = task["dataset"]
            products = [items] if isinstance(items, str) else items
            if not isinstance(products, list) or not products:
                raise ValueError(f"{key}: dataset must name at least one product")
            for dataset in products:
                reference(dataset, projects[task["project"]]["datasets"], key)
            tasks[key] = products

    for filename, asset in assets:
        dataset = asset["dataset"]
        reference(dataset, datasets, filename)
        reference(asset["storage_id"], stores, filename)
        relative = asset["relative_path"]
        if (not relative or PureWindowsPath(relative).anchor or "\\" in relative
                or ".." in PurePosixPath(relative).parts):
            raise ValueError(f"{filename}: invalid relative_path {relative!r}")
        if "task_id" in asset:
            key = asset["task_id"]
            reference(key, tasks, filename)
            reference(dataset, tasks[key], f"{filename}: {key}")

    return (f"OK: {len(projects)} projects, {len(datasets)} datasets, "
            f"{len(tasks)} research tasks, {len(assets)} research assets")
