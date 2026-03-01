import csv
import json
import re
from pathlib import Path


# -------- Helpers --------
def load_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def norm(s: str) -> str:
    return s.lower()


def is_valid_asset_id(asset_id: str) -> bool:
    # Filter internal/state ids
    if asset_id.startswith("*"):
        return False
    return True


# -------- Classification rules --------
# Material detection from IDs (works for Ore_*, Ingredient_Bar_*, Armor_Mithril_*, etc.)
MATERIALS = [
    "copper",
    "iron",
    "thorium",
    "cobalt",
    "silver",
    "gold",
    "adamantite",
    "mithril",
    "onyxium",
    "prisma",
    "prism",
    "bronze",
    "steel",
]


def detect_material(asset_id: str) -> str | None:
    s = norm(asset_id)
    if "prism" in s:
        return "prisma"
    for m in MATERIALS:
        if m in s:
            return m
    return None


def detect_hide_leather_tier(asset_id: str) -> str | None:
    s = norm(asset_id)
    if "prism" in s or "prisma" in s:
        return "prism"
    for t in ["light", "medium", "heavy", "storm"]:
        if t in s:
            return t
    return None


# Category detection
def detect_category(kind: str, asset_id: str) -> str:
    s = norm(asset_id)

    if kind == "block":
        if s.startswith("ore_"):
            return "ore_block"
        if any(
            x in s
            for x in [
                "stone",
                "basalt",
                "shale",
                "slate",
                "sandstone",
                "marble",
                "volcanic",
                "magma",
            ]
        ):
            return "terrain_block"
        return "block_misc"

    if kind == "resource":
        # e.g. Wood_Trunk, Plant_Fiber etc.
        if "wood" in s or "trunk" in s or "log" in s:
            return "wood_resource"
        if "fiber" in s:
            return "fiber_resource"
        return "resource_misc"

    # kind == "item"
    if "ingredient_stick" in s:
        return "basic_item"
    if "ingredient_fibre" in s or "ingredient_fiber" in s:
        return "basic_item"
    if "ingredient_tree_sap" in s:
        return "basic_item"
    if "ingredient_hide" in s:
        return "hide_item"
    if "ingredient_leather" in s:
        return "leather_item"
    if "ingredient_fabric_scrap" in s or "fabric_scrap" in s:
        return "cloth_item"
    if "ingredient_bolt" in s and ("linen" in s or "shadow" in s or "cinder" in s):
        return "cloth_item"
    if "ingredient_bar_" in s or "bar_" in s or "ingot" in s:
        return "bar_item"
    if "seed" in s:
        return "seed_item"
    if any(x in s for x in ["wheat", "potato", "carrot", "chili", "apple", "sunflower"]):
        return "crop_item"
    if s.startswith("armor_") or "armor_" in s:
        return "armor_item"
    if s.startswith("weapon_") or "weapon_" in s:
        return "weapon_item"
    if "ore_" in s:
        return "ore_item"
    return "item_misc"


# Default zone & rarity mapping by material tier
# (du kannst das später feinjustieren, aber als Start extrem brauchbar)
TIER = {
    # Zone 1–2
    "copper": (1, "common", "ore_t1"),
    "iron": (1, "common", "ore_t1"),
    "bronze": (1, "common", "t1_crafted"),
    # Zone 2–3
    "thorium": (2, "uncommon", "ore_t2"),
    "silver": (2, "uncommon", "ore_t2"),
    "gold": (3, "rare", "ore_t3"),
    "cobalt": (3, "rare", "ore_t3"),
    # Zone 3–4
    "adamantite": (3, "very_rare", "ore_t4"),
    "mithril": (4, "very_rare", "endgame_mithril"),
    "onyxium": (4, "mythic", "endgame_onyxium"),
    "prisma": (4, "mythic", "endgame_prisma"),
    "steel": (2, "uncommon", "t2_crafted"),
}


# Profiles for non-material classes
DEFAULT_PROFILES = {
    "terrain_block": (1, "very_common", "mass_block"),
    "ore_block": (None, None, None),  # filled from material tier
    "wood_resource": (1, "common", "wood_basic"),
    "fiber_resource": (1, "common", "fiber_basic"),
    "basic_item": (1, "common", "basic_gather"),
    "hide_item": (None, None, "hide_drop"),
    "leather_item": (None, None, "leather_processing"),
    "cloth_item": (None, None, "cloth_processing"),
    "bar_item": (None, None, "bar_from_ore"),  # zone/rarity from material
    "seed_item": (1, "common", "seed"),
    "crop_item": (1, "common", "crop"),
    "armor_item": (None, None, "gear"),  # zone/rarity from material if present
    "weapon_item": (None, None, "gear"),
    "item_misc": (1, "common", "misc"),
    "block_misc": (1, "common", "misc"),
    "resource_misc": (1, "common", "misc"),
    "ore_item": (None, None, "ore_item"),
}

TIER_APPLIES_TO = {"ore_block", "ore_item", "bar_item"}


def assign_zone_rarity_profile(kind: str, category: str, material: str | None, asset_id: str):
    # Start with category defaults
    z, r, p = DEFAULT_PROFILES.get(category, (1, "common", "misc"))

    # Override via material tier only for ore/bar categories (NOT gear)
    if material and material in TIER and category in TIER_APPLIES_TO:
        tz, tr, tp = TIER[material]
        # zone/rarity always derive from tier if meaningful
        z = tz if z is None else max(z, tz)  # keep higher if category already implies higher
        r = tr if r is None else tr
        # profile: ore tiers or endgame materials win
        p = tp if tp else p

    # Special case: ore blocks without material detected -> keep generic
    if category == "ore_block" and not material:
        z = 2
        r = "uncommon"
        p = "ore_unknown"

    # Special case: "bar_from_ore" but no material -> generic processing
    if category == "bar_item" and not material:
        z = 2
        r = "uncommon"
        p = "bar_generic"

    # Hide/leather tiers (best-effort)
    if category in ("hide_item", "leather_item"):
        tier = detect_hide_leather_tier(asset_id)
        if tier == "light":
            z, r = 1, "uncommon"
            p = "hide_drop_t1" if category == "hide_item" else "leather_processing"
        elif tier == "medium":
            z, r = 2, "uncommon"
            p = "hide_drop_t2" if category == "hide_item" else "leather_processing"
        elif tier == "heavy":
            z, r = 2, "rare"
            p = "hide_drop_t3" if category == "hide_item" else "leather_processing"
        elif tier == "storm":
            z, r = 3, "rare"
            p = "hide_drop_storm" if category == "hide_item" else "leather_processing"
        elif tier == "prism":
            z, r = 4, "very_rare"
            p = "hide_drop_prism" if category == "hide_item" else "leather_processing"

    if category == "cloth_item":
        if "shadow" in norm(asset_id):
            z, r, p = 3, "rare", "cloth_processing"
        elif "cinder" in norm(asset_id):
            z, r, p = 2, "uncommon", "cloth_processing"
        elif "linen" in norm(asset_id):
            z, r, p = 1, "common", "cloth_processing"

    return z, r, p


def main() -> None:
    base = Path("data/extracted")
    item_ids = load_list(base / "item_ids.json")
    resource_ids = load_list(base / "resource_type_ids.json")
    block_ids = load_list(base / "block_type_ids.json")

    rows = []

    def add(kind: str, asset_id: str) -> None:
        if not is_valid_asset_id(asset_id):
            return
        category = detect_category(kind, asset_id)
        material = detect_material(asset_id)
        zone, rarity, profile = assign_zone_rarity_profile(kind, category, material, asset_id)
        rows.append(
            {
                "id": asset_id,
                "kind": kind,
                "category": category,
                "material": material or "",
                "default_zone": zone,
                "rarity_tag": rarity,
                "profile": profile,
            }
        )

    for x in item_ids:
        add("item", x)
    for x in resource_ids:
        add("resource", x)
    for x in block_ids:
        add("block", x)

    # Write catalog
    out_csv = base / "catalog.csv"
    write_csv(out_csv, rows)

    # Small summary report (counts)
    summary = {}
    for r in rows:
        key = (r["kind"], r["category"], r["profile"])
        summary[key] = summary.get(key, 0) + 1

    out_summary = base / "catalog_summary.json"
    out_summary.write_text(
        json.dumps({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in summary.items()}, indent=2),
        encoding="utf-8",
    )

    print(f"Wrote: {out_csv}")
    print(f"Wrote: {out_summary}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
