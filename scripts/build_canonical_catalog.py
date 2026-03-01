import csv
import re
from pathlib import Path

ORE_RE = r"^Ore_([A-Za-z0-9]+)_"  # Ore_Cobalt_Basalt -> cobalt
ING_BAR_RE = r"^Ingredient_Bar_([A-Za-z0-9]+)$"
SEED_RE = r"seed"  # simple heuristic
CROP_WORDS = ["wheat", "potato", "carrot", "chili", "apple", "sunflower"]
WOOD_WORDS = ["wood", "trunk", "log"]


def norm(s: str) -> str:
    return s.lower()


def canonicalize(row: dict) -> tuple[str, str] | None:
    """return (canonical_key, canonical_kind)"""
    asset_id = row["id"]
    kind = row["kind"]
    category = row["category"]
    material = row.get("material", "").strip().lower()

    s = norm(asset_id)

    # Basics
    if "ingredient_stick" in s:
        return "BASIC:stick", "basic"
    if "ingredient_fibre" in s or "ingredient_fiber" in s:
        return "BASIC:plant_fiber", "basic"
    if "ingredient_tree_sap" in s:
        return "BASIC:tree_sap", "basic"

    # Hides / Leather
    if "ingredient_hide" in s:
        if "prism" in s or "prisma" in s:
            return "HIDE:prism", "hide"
        for t in ["storm", "heavy", "medium", "light"]:
            if t in s:
                return f"HIDE:{t}", "hide"
        return "HIDE:generic", "hide"
    if "ingredient_leather" in s:
        if "prism" in s or "prisma" in s:
            return "LEATHER:prism", "leather"
        for t in ["storm", "heavy", "medium", "light"]:
            if t in s:
                return f"LEATHER:{t}", "leather"
        return "LEATHER:generic", "leather"

    # Cloth / Scraps
    if "fabric_scrap" in s or "ingredient_fabric_scrap" in s:
        if "shadow" in s:
            return "CLOTH:shadow_weave", "cloth"
        if "cinder" in s:
            return "CLOTH:cinder_cloth", "cloth"
        if "linen" in s:
            return "CLOTH:linen_scraps", "cloth"
        return "CLOTH:scraps", "cloth"
    if "ingredient_bolt" in s and ("linen" in s or "shadow" in s or "cinder" in s):
        if "shadow" in s:
            return "CLOTH:shadow_weave", "cloth"
        if "cinder" in s:
            return "CLOTH:cinder_cloth", "cloth"
        if "linen" in s:
            return "CLOTH:linen_scraps", "cloth"
        return "CLOTH:bolt", "cloth"

    # Crystals & Gems
    if "ingredient_crystal_" in s:
        t = s.replace("ingredient_crystal_", "")
        return f"CRYSTAL:{t}", "crystal"
    if s.startswith("rock_gem_") or "rock_gem_" in s:
        t = s.replace("rock_gem_", "")
        return f"GEM:{t}", "gem"

    # Ore blocks/items: map to ORE_MATERIAL:<material>
    if category == "ore_block":
        if material:
            return f"ORE_MATERIAL:{material}", "ore_material"
        return "ORE_MATERIAL:unknown", "ore_material"

    # Ore items: keep craft-only ores as ORE_ITEM, otherwise as material
    if category == "ore_item":
        if material == "prisma":
            return None
        if material in ("onyxium", "mithril"):
            return f"ORE_ITEM:{asset_id}", "ore_item"
        if material:
            return f"ORE_MATERIAL:{material}", "ore_material"
        return f"ORE_ITEM:{asset_id}", "ore_item"

    # Bars
    if category == "bar_item":
        if material:
            return f"BAR:{material}", "bar"
        return "BAR:generic", "bar"

    # Seeds
    if category == "seed_item":
        # keep specific seeds as-is for now
        return f"SEED:{asset_id}", "seed"

    # Crops (best effort)
    if category == "crop_item":
        m = None
        for w in CROP_WORDS:
            if w in s:
                m = w
                break
        return (f"CROP:{m}" if m else f"CROP:{asset_id}", "crop")

    # Wood resources
    if kind == "resource" and category == "wood_resource":
        return f"RESOURCE:{asset_id}", "resource"

    # Terrain mass blocks -> group by rough family
    if kind == "block" and category == "terrain_block":
        # group common families to reduce noise
        fam = None
        for w in [
            "stone",
            "basalt",
            "shale",
            "slate",
            "sandstone",
            "marble",
            "volcanic",
            "magma",
        ]:
            if w in s:
                fam = w
                break
        return (f"MASS:{fam}" if fam else "MASS:other", "mass")

    # Essences (best effort): Ingredient_Void_Essence / Essence_Life etc.
    if "essence" in s:
        # try detect type
        et = None
        for t in ["life", "void", "fire", "water", "ice", "earth", "air", "storm"]:
            if t in s:
                et = t
                break
        return (f"ESSENCE:{et}" if et else "ESSENCE:generic", "essence")

    # Default: keep as-is (we will refine later)
    return f"{kind.upper()}:{asset_id}", "raw"


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
