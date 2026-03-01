import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

ITEM_ID_PATTERNS = [
    re.compile(r'"ItemId"\s*:\s*"([^"]+)"'),
    re.compile(r'"itemId"\s*:\s*"([^"]+)"'),
    re.compile(r'"Id"\s*:\s*"([^"]+)"'),
    re.compile(r'"id"\s*:\s*"([^"]+)"'),
]

# Heuristik: wir wollen nicht jede "id" im ganzen Mod fangen,
# also filtern wir auf Dateien/Jsons, die typisch Item-Definitionen enthalten.
LIKELY_ITEM_FILE_HINTS = [
    "item",
    "items",
    "itemtype",
    "itemtypes",
    "icons/item",
    "server/items",
    "assets/items",
]


def is_likely_item_file(path_str: str) -> bool:
    s = path_str.lower()
    if not s.endswith(".json"):
        return False
    return any(h in s for h in LIKELY_ITEM_FILE_HINTS)


def extract_from_text(text: str) -> set[str]:
    found = set()
    for pat in ITEM_ID_PATTERNS:
        for m in pat.finditer(text):
            val = m.group(1).strip()
            # Grobe Plausibilitätsfilter
            if len(val) < 3:
                continue
            if any(ch.isspace() for ch in val):
                continue
            found.add(val)
    return found


def scan_zip(file_path: Path) -> set[str]:
    out = set()
    try:
        with ZipFile(file_path, "r") as z:
            for name in z.namelist():
                if not is_likely_item_file(name):
                    continue
                try:
                    data = z.read(name)
                    text = data.decode("utf-8", errors="ignore")
                    out |= extract_from_text(text)
                except Exception:
                    continue
    except BadZipFile:
        pass
    return out


def scan_folder(folder: Path) -> set[str]:
    out = set()
    for p in folder.rglob("*.json"):
        if not is_likely_item_file(str(p)):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
            out |= extract_from_text(text)
        except Exception:
            continue
    return out


def main() -> None:
    raw_dir = Path("data/raw")
    if not raw_dir.exists():
        print("Missing data/raw. Create it and put your mods/assets there.")
        sys.exit(1)

    found = set()

    # Scan folders
    for p in raw_dir.iterdir():
        if p.is_dir():
            found |= scan_folder(p)

    # Scan archives (.zip/.jar)
    for ext in ("*.zip", "*.jar"):
        for p in raw_dir.rglob(ext):
            found |= scan_zip(p)

    out_dir = Path("data/extracted")
    out_dir.mkdir(parents=True, exist_ok=True)

    items = sorted(found)
    (out_dir / "items.json").write_text(
        json.dumps(items, indent=2), encoding="utf-8"
    )
    (out_dir / "items.txt").write_text("\n".join(items), encoding="utf-8")

    print(f"Found {len(items)} unique item ids.")
    print(f"Wrote: {out_dir / 'items.json'} and items.txt")


if __name__ == "__main__":
    main()
