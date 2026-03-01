import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile


def is_json(name: str) -> bool:
    return name.lower().endswith(".json")


def read_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None


def read_text_from_zip(z: ZipFile, name: str) -> str | None:
    try:
        return z.read(name).decode("utf-8", errors="ignore")
    except Exception:
        return None


def extract_recipe(obj: dict) -> dict | None:
    r = obj.get("Recipe")
    if not isinstance(r, dict):
        return None

    inputs = []
    for inp in r.get("Input", []) or []:
        if not isinstance(inp, dict):
            continue
        qty = int(inp.get("Quantity", 0) or 0)
        if qty <= 0:
            continue
        if "ItemId" in inp:
            inputs.append({"type": "item", "id": inp["ItemId"], "qty": qty})
        elif "ResourceTypeId" in inp:
            inputs.append({"type": "resource", "id": inp["ResourceTypeId"], "qty": qty})

    if not inputs:
        return None

    return {
        "time_seconds": float(r.get("TimeSeconds", 0) or 0),
        "knowledge_required": bool(r.get("KnowledgeRequired", False)),
        "output_qty": int(r.get("OutputQuantity", 1) or 1),
        "inputs": inputs,
    }


def extract_item_id(obj: dict, fallback: str) -> str:
    for key in ("ItemId", "Id", "Identifier"):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def source_priority(path: Path) -> int:
    s = str(path).replace("\\", "/").lower()
    if "/endgame/" in s:
        return 3
    return 1


def main() -> None:
    raw = Path("data/raw")
    if not raw.exists():
        raise SystemExit("Missing data/raw")

    recipes = {}  # item_id -> recipe
    sources = {}  # item_id -> (priority, path)
    skip_ids = {"Ore_Prisma"}

    # Scan folders
    for p in raw.rglob("*.json"):
        text = read_text(p)
        if not text:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue

        recipe = extract_recipe(obj)
        if not recipe:
            continue

        item_id = extract_item_id(obj, p.stem)
        if item_id in skip_ids:
            continue
        prio = source_priority(p)
        prev = sources.get(item_id)
        if (prev is None) or (prio > prev[0]):
            recipes[item_id] = recipe
            sources[item_id] = (prio, str(p))

    # Scan archives (.zip/.jar)
    for ext in ("*.zip", "*.jar"):
        for zpath in raw.rglob(ext):
            try:
                with ZipFile(zpath, "r") as z:
                    for name in z.namelist():
                        if not is_json(name):
                            continue
                        text = read_text_from_zip(z, name)
                        if not text:
                            continue
                        try:
                            obj = json.loads(text)
                        except Exception:
                            continue
                        if not isinstance(obj, dict):
                            continue
                        recipe = extract_recipe(obj)
                        if not recipe:
                            continue
                        item_id = extract_item_id(obj, Path(name).stem)
                        if item_id in skip_ids:
                            continue
                        prio = 1
                        prev = sources.get(item_id)
                        if (prev is None) or (prio > prev[0]):
                            recipes[item_id] = recipe
                            sources[item_id] = (prio, f"{zpath}:{name}")
            except BadZipFile:
                continue

    out = Path("data/extracted/recipes.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recipes, indent=2), encoding="utf-8")

    print(f"Wrote recipes: {out} ({len(recipes)} entries)")


if __name__ == "__main__":
    main()
