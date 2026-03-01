import csv
import json
import re
import sys
from pathlib import Path

# Order matters: first match wins.
CATEGORY_RULES = [
    ("ore", re.compile(r"(?:^|[_:])ore$|(?:^|[_:])ore[_:]")),
    ("ingot", re.compile(r"(?:^|[_:])ingot$|(?:^|[_:])ingot[_:]")),
    ("seed", re.compile(r"(?:^|[_:])seed[_:]|(?:^|[_:])seed$")),
    ("crop", re.compile(r"(?:^|[_:])crop[_:]|(?:^|[_:])crop$")),
    ("log", re.compile(r"(?:^|[_:])log[_:]|(?:^|[_:])log$")),
    ("plank", re.compile(r"(?:^|[_:])plank[_:]|(?:^|[_:])plank$")),
    ("food", re.compile(r"(?:^|[_:])food[_:]|(?:^|[_:])food$")),
    ("tool", re.compile(r"(?:^|[_:])tool[_:]|(?:^|[_:])tool$")),
    ("armor", re.compile(r"(?:^|[_:])armor[_:]|(?:^|[_:])armor$")),
    ("weapon", re.compile(r"(?:^|[_:])sword[_:]|(?:^|[_:])bow[_:]|(?:^|[_:])weapon")),
    ("potion", re.compile(r"(?:^|[_:])potion[_:]|(?:^|[_:])potion$")),
    ("gem", re.compile(r"(?:^|[_:])gem[_:]|(?:^|[_:])gem$")),
    ("relic", re.compile(r"(?:^|[_:])relic[_:]|(?:^|[_:])relic$")),
]

# Namespace/profile mapping (example: endgameqol:* => profile "endgameqol").
PROFILE_RULES = [
    ("endgameqol", re.compile(r"^endgameqol:")),
]

DEFAULT_ZONE_BY_CATEGORY = {
    "ore": 2,
    "ingot": 2,
    "seed": 1,
    "crop": 1,
    "log": 1,
    "plank": 1,
    "food": 1,
    "tool": 2,
    "armor": 3,
    "weapon": 3,
    "potion": 2,
    "gem": 3,
    "relic": 4,
}

DEFAULT_RARITY_BY_CATEGORY = {
    "ore": "common",
    "ingot": "common",
    "seed": "common",
    "crop": "common",
    "log": "very_common",
    "plank": "very_common",
    "food": "common",
    "tool": "uncommon",
    "armor": "rare",
    "weapon": "rare",
    "potion": "uncommon",
    "gem": "rare",
    "relic": "very_rare",
}


def classify_category(item_id: str) -> str:
    s = item_id.lower()
    for cat, pat in CATEGORY_RULES:
        if pat.search(s):
            return cat
    return "misc"


def classify_profile(item_id: str) -> str:
    s = item_id.lower()
    for profile, pat in PROFILE_RULES:
        if pat.search(s):
            return profile
    return "default"


def default_zone_for(category: str) -> int:
    return DEFAULT_ZONE_BY_CATEGORY.get(category, 1)


def default_rarity_for(category: str) -> str:
    return DEFAULT_RARITY_BY_CATEGORY.get(category, "common")


def main() -> None:
    items_path = Path("data/extracted/items.json")
    if not items_path.exists():
        print("Missing data/extracted/items.json. Run extract_items.py first.")
        sys.exit(1)

    items = json.loads(items_path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        print("items.json is not a list.")
        sys.exit(1)

    out_dir = Path("data/extracted")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "item_taxonomy.csv"

    rows = []
    for item_id in items:
        if not isinstance(item_id, str):
            continue
        category = classify_category(item_id)
        profile = classify_profile(item_id)
        default_zone = default_zone_for(category)
        rarity_tag = default_rarity_for(category)
        rows.append(
            {
                "item_id": item_id,
                "category": category,
                "default_zone": default_zone,
                "rarity_tag": rarity_tag,
                "profile": profile,
            }
        )

    rows.sort(key=lambda r: r["item_id"].lower())

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["item_id", "category", "default_zone", "rarity_tag", "profile"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
