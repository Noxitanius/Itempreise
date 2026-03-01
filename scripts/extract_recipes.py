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
        "inputs": inputs,
    }


def main() -> None:
    raw = Path("data/raw")
    if not raw.exists():
        raise SystemExit("Missing data/raw")

    recipes = {}  # item_id -> recipe

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

        # Fallback id: filename stem
        item_id = p.stem
        recipes[item_id] = recipe

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
                        item_id = Path(name).stem
                        recipes[item_id] = recipe
            except BadZipFile:
                continue

    out = Path("data/extracted/recipes.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(recipes, indent=2), encoding="utf-8")

    print(f"Wrote recipes: {out} ({len(recipes)} entries)")


if __name__ == "__main__":
    main()
