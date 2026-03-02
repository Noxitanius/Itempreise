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


def extract_item_id(obj: dict, fallback: str) -> str:
    for key in ("ItemId", "Id", "Identifier"):
        v = obj.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return fallback


def main() -> None:
    raw = Path("data/raw")
    if not raw.exists():
        raise SystemExit("Missing data/raw")

    icons: dict[str, str] = {}

    # Folders
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
        icon = obj.get("Icon")
        if not isinstance(icon, str) or not icon.strip():
            continue
        item_id = extract_item_id(obj, p.stem)
        icons[item_id] = icon

    # Archives (.zip/.jar)
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
                        icon = obj.get("Icon")
                        if not isinstance(icon, str) or not icon.strip():
                            continue
                        item_id = extract_item_id(obj, Path(name).stem)
                        icons[item_id] = icon
            except BadZipFile:
                continue

    out = Path("data/extracted/item_icons.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(icons, indent=2), encoding="utf-8")

    print(f"Wrote icons: {out} ({len(icons)} entries)")


if __name__ == "__main__":
    main()
