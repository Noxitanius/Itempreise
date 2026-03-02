import csv
import re
from pathlib import Path

ORE_RE = r"^Ore_([A-Za-z0-9]+)_"  # Ore_Cobalt_Basalt -> cobalt
ING_BAR_RE = r"^Ingredient_Bar_([A-Za-z0-9]+)$"
SEED_RE = r"seed"  # simple heuristic
CROP_WORDS = [
    "wheat",
    "potato",
    "carrot",
    "chili",
    "apple",
    "sunflower",
    "berry",
    "berries",
]
WOOD_WORDS = ["wood", "trunk", "log"]


def norm(s: str) -> str:
    return s.lower()


def canonicalize(row: dict) -> tuple[str, str] | None:
    """return (canonical_id, canonical_kind) where canonical_id == original asset id"""
    asset_id = row["id"]
    kind = row["kind"]
    category = row["category"]
    material = row.get("material", "").strip().lower()

    s = norm(asset_id)

    # Exclusions
    if asset_id.startswith("Salvage_"):
        return None
    if s.startswith("plant_") and "_stage_" in s:
        return None
    if s.startswith("plant_crop_") and s.endswith("_block"):
        return None
    if s.startswith("ore_") and any(k in s for k in ("_basalt", "_magma", "_shale", "_slate", "_stone", "_volcanic", "_sandstone", "_calcite", "_mud")):
        return None
    if category == "ore_block" and material in ("mithril", "onyxium", "prisma"):
        return None
    if category == "ore_item" and material == "prisma":
        return None

    # Kind mapping (keep original ids)
    if category == "bar_item":
        return asset_id, "bar"
    if category == "ore_block":
        return asset_id, "ore_material"
    if category == "ore_item":
        if material in ("onyxium", "mithril"):
            return asset_id, "ore_item"
        return asset_id, "ore_material"
    if category == "seed_item":
        return asset_id, "seed"
    if category == "crop_item":
        return asset_id, "crop"
    if category == "basic_item":
        return asset_id, "basic"
    if category == "hide_item":
        return asset_id, "hide"
    if category == "leather_item":
        return asset_id, "leather"
    if category == "cloth_item":
        return asset_id, "cloth"
    if category == "crystal_item":
        return asset_id, "crystal"
    if category == "gem_item":
        return asset_id, "gem"
    if category == "potion_item":
        return asset_id, "potion"
    if category in ("armor_item", "weapon_item", "tool_item"):
        return asset_id, "gear"

    # Resources / blocks
    if kind == "resource":
        if category == "wood_resource":
            return asset_id, "resource"
        if "rock" in s or "rubble" in s:
            return asset_id, "mass"
        return asset_id, "resource"
    if kind == "block" and category == "terrain_block":
        return asset_id, "mass"

    # Essences
    if "essence" in s:
        return asset_id, "essence"

    # Default: keep as-is
    return asset_id, "raw"


def main() -> None:
    src = Path("data/extracted/catalog.csv")
    if not src.exists():
        raise SystemExit("Missing data/extracted/catalog.csv")

    out = Path("data/extracted/canonical_catalog.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    agg: dict[str, dict] = {}

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            res = canonicalize(row)
            if res is None:
                continue
            key, ckind = res

            # Aggregate: keep max zone, max rarity "weight" via tag order, and count variants
            zone_raw = row.get("default_zone", "").strip()
            z = int(zone_raw) if zone_raw else 1
            rarity = row["rarity_tag"]
            profile = row["profile"]

            rec = agg.get(key)
            if not rec:
                agg[key] = {
                    "canonical_id": key,
                    "canonical_kind": ckind,
                    "source_count": 1,
                    "max_zone": z,
                    "rarity_tag": rarity,
                    "dominant_profile": profile,
                }
            else:
                rec["source_count"] += 1
                rec["max_zone"] = max(rec["max_zone"], z)
                # Keep the "rarest" tag by fixed order (unknown -> lowest)
                order = ["very_common", "common", "uncommon", "rare", "very_rare", "mythic"]
                r_new = rarity if rarity in order else "common"
                r_cur = rec["rarity_tag"] if rec["rarity_tag"] in order else "common"
                if order.index(r_new) > order.index(r_cur):
                    rec["rarity_tag"] = r_new
                # Prefer non-misc profiles as dominant
                if rec["dominant_profile"] == "misc" and profile != "misc":
                    rec["dominant_profile"] = profile

    # Write
    with out.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "canonical_id",
            "canonical_kind",
            "source_count",
            "max_zone",
            "rarity_tag",
            "dominant_profile",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for rec in sorted(agg.values(), key=lambda r: r["canonical_id"]):
            w.writerow(rec)

    print(f"Canonical rows: {len(agg)}")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
