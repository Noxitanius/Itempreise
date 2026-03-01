import json
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

# --- Patterns ---
ITEM_ID_KEYS = ("ItemId", "itemId")
RESOURCE_TYPE_KEYS = ("ResourceTypeId", "resourceTypeId", "ResourceTypeID", "resourceTypeID")

# BlockTypeList files typically contain lists like {"Blocks":[...]} or similar.
BLOCK_LIST_KEYS = ("Blocks", "BlockTypes", "blockTypes", "blocks")

# General ID patterns (fallback)
PATTERNS = {
    "item": [
        re.compile(r'"ItemId"\s*:\s*"([^"]+)"'),
        re.compile(r'"itemId"\s*:\s*"([^"]+)"'),
    ],
    "resource_type": [
        re.compile(r'"ResourceTypeId"\s*:\s*"([^"]+)"'),
        re.compile(r'"resourceTypeId"\s*:\s*"([^"]+)"'),
    ],
}


def looks_like_asset_id(s: str) -> bool:
    # Accept: Ore_Copper_Stone, Ingredient_Bar_Mithril, Wood_Trunk, modid:thing
    if len(s) < 3:
        return False
    if any(ch.isspace() for ch in s):
        return False
    # Avoid obvious junk
    bad = {"TODO", "EMPTY", "Empty", "None", "null"}
    if s in bad:
        return False
    return True


def is_json(path: str) -> bool:
    return path.lower().endswith(".json")


def extract_json_lists(text: str, key: str) -> set[str]:
    # super pragmatic: try to parse JSON, then read arrays under the key
    out = set()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
            for v in obj[key]:
                if isinstance(v, str) and looks_like_asset_id(v):
                    out.add(v)
    except Exception:
        pass
    return out


def extract_from_text(text: str) -> tuple[set[str], set[str], set[str]]:
    item_ids = set()
    resource_type_ids = set()
    block_type_ids = set()

    # Regex extraction for ItemId / ResourceTypeId occurrences anywhere
    for pat in PATTERNS["item"]:
        for m in pat.finditer(text):
            v = m.group(1).strip()
            if looks_like_asset_id(v):
                item_ids.add(v)

    for pat in PATTERNS["resource_type"]:
        for m in pat.finditer(text):
            v = m.group(1).strip()
            if looks_like_asset_id(v):
                resource_type_ids.add(v)

    # If file looks like BlockTypeList, parse "Blocks" list
    # We'll attempt for any of the known list keys
    for key in BLOCK_LIST_KEYS:
        block_type_ids |= extract_json_lists(text, key)

    return item_ids, resource_type_ids, block_type_ids


def read_text_from_zip(z: ZipFile, name: str) -> str | None:
    try:
        data = z.read(name)
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return None


def scan_zip(file_path: Path) -> tuple[set[str], set[str], set[str]]:
    item_ids = set()
    resource_type_ids = set()
    block_type_ids = set()

    try:
        with ZipFile(file_path, "r") as z:
            for name in z.namelist():
                if not is_json(name):
                    continue
                text = read_text_from_zip(z, name)
                if not text:
                    continue
                a, b, c = extract_from_text(text)
                item_ids |= a
                resource_type_ids |= b
                block_type_ids |= c
    except BadZipFile:
        pass

    return item_ids, resource_type_ids, block_type_ids


def scan_folder(folder: Path) -> tuple[set[str], set[str], set[str]]:
    item_ids = set()
    resource_type_ids = set()
    block_type_ids = set()

    for p in folder.rglob("*.json"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        a, b, c = extract_from_text(text)
        item_ids |= a
        resource_type_ids |= b
        block_type_ids |= c

    return item_ids, resource_type_ids, block_type_ids


def write_sorted(path: Path, values: set[str]) -> None:
    items = sorted(values)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")


def main() -> None:
    raw_dir = Path("data/raw")
    if not raw_dir.exists():
        print("Missing data/raw. Create it and put your mods/assets there.")
        sys.exit(1)

    item_ids = set()
    resource_type_ids = set()
    block_type_ids = set()

    # Folders
    for p in raw_dir.iterdir():
        if p.is_dir():
            a, b, c = scan_folder(p)
            item_ids |= a
            resource_type_ids |= b
            block_type_ids |= c

    # Archives (.zip/.jar)
    for ext in ("*.zip", "*.jar"):
        for p in raw_dir.rglob(ext):
            a, b, c = scan_zip(p)
            item_ids |= a
            resource_type_ids |= b
            block_type_ids |= c

    out_dir = Path("data/extracted")
    out_dir.mkdir(parents=True, exist_ok=True)

    write_sorted(out_dir / "item_ids.json", item_ids)
    write_sorted(out_dir / "resource_type_ids.json", resource_type_ids)
    write_sorted(out_dir / "block_type_ids.json", block_type_ids)

    print(f"Items:          {len(item_ids)}")
    print(f"ResourceTypes:  {len(resource_type_ids)}")
    print(f"BlockTypes:     {len(block_type_ids)}")
    print("Wrote data/extracted/{item_ids,resource_type_ids,block_type_ids}.json")


if __name__ == "__main__":
    main()
