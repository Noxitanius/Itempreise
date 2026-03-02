import csv
from pathlib import Path
import yaml

RARITY_ORDER = ["very_common", "common", "uncommon", "rare", "very_rare", "mythic"]


def load_policy(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_icons(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def rarity_factor(policy: dict, rarity_tag: str) -> float:
    return float(policy["rarity"].get(rarity_tag, 1.0))


def zone_factor(policy: dict, zone: int) -> float:
    return float(policy["zones"][zone]["risk_factor"])


def bundle_for(canonical_kind: str, canonical_id: str) -> int:
    if canonical_kind == "mass":
        return 1000
    if canonical_id.startswith("ORE_MATERIAL:") or canonical_id.startswith("BAR:"):
        return 100
    if canonical_id.startswith("CROP:"):
        return 1000
    return 1


def minutes_per_unit(profile: str, canonical_kind: str, canonical_id: str) -> float | None:
    # v0.1: only price the economically meaningful groups; leave the rest unpriced
    if canonical_kind == "mass":
        return 0.002
    if canonical_id.startswith("ORE_MATERIAL:"):
        # derive by profile
        if profile == "ore_t1":
            return 0.05
        if profile == "ore_t2":
            return 0.08
        if profile == "ore_t3":
            return 0.12
        if profile == "ore_t4":
            return 0.18
        if profile == "endgame_mithril":
            return 0.25
        if profile == "endgame_onyxium":
            return 0.35
        if profile == "endgame_prisma":
            return 0.50
        # unknown ore
        return 0.10

    if canonical_id.startswith("BAR:"):
        # bars track their material tier; use same as ore tier but slightly higher (processing)
        bump = 1.15
        base = 0.10
        if profile == "ore_t1":
            base = 0.05
        elif profile == "ore_t2":
            base = 0.08
        elif profile == "ore_t3":
            base = 0.12
        elif profile == "ore_t4":
            base = 0.18
        elif profile == "endgame_mithril":
            base = 0.25
        elif profile == "endgame_onyxium":
            base = 0.35
        elif profile == "endgame_prisma":
            base = 0.50
        return base * bump

    if canonical_id.startswith("CROP:"):
        return 0.012

    if canonical_kind in ("resource",):
        # wood/fiber etc.
        if (
            "wood" in canonical_id.lower()
            or "trunk" in canonical_id.lower()
            or "log" in canonical_id.lower()
        ):
            return 0.01
        return 0.01
    if canonical_id == "BASIC:charcoal":
        return 0.0

    # leave raw/misc unpriced for now
    return None


def apply_guardrails(
    policy: dict, canonical_id: str, canonical_kind: str, bundle_qty: int, price: float
) -> float:
    # Mass cap per 1000
    if canonical_kind == "mass":
        cap = float(policy["guardrails"].get("mass_goods_cap_nyra_per_1000", 3.0))
        # price is already for bundle (1000)
        return min(price, cap)

    # Endgame floors (per 100)
    if canonical_id.startswith("BAR:") or canonical_id.startswith("ORE_MATERIAL:"):
        key = canonical_id.split(":", 1)[1].lower()
        if key == "mithril":
            return max(price, 40.0)
        if key == "onyxium":
            return max(price, 80.0)
        if key == "prisma":
            return max(price, 140.0)

    return price


def canonical_to_item_id(canonical_id: str) -> str | None:
    if canonical_id.startswith("BAR:"):
        mat = canonical_id.split(":", 1)[1]
        return f"Ingredient_Bar_{mat.capitalize()}"
    if canonical_id.startswith("ORE_ITEM:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id.startswith("ORE_MATERIAL:"):
        mat = canonical_id.split(":", 1)[1]
        return f"Ore_{mat.capitalize()}"
    if canonical_id.startswith("ARMOR:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id.startswith("WEAPON:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id.startswith("TOOL:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id.startswith("CRYSTAL:"):
        t = canonical_id.split(":", 1)[1]
        return f"Ingredient_Crystal_{t.capitalize()}"
    if canonical_id.startswith("GEM:"):
        t = canonical_id.split(":", 1)[1]
        return f"Rock_Gem_{t.capitalize()}"
    if canonical_id.startswith("ESSENCE:"):
        t = canonical_id.split(":", 1)[1]
        return f"Ingredient_{t.capitalize()}_Essence"
    if canonical_id == "BASIC:charcoal":
        return "Ingredient_Charcoal"
    if canonical_id == "BASIC:stick":
        return "Ingredient_Stick"
    if canonical_id == "BASIC:plant_fiber":
        return "Ingredient_Fibre"
    if canonical_id == "BASIC:tree_sap":
        return "Ingredient_Tree_Sap"
    if canonical_id.startswith("HIDE:"):
        t = canonical_id.split(":", 1)[1]
        if t == "prism":
            return "Ingredient_Hide_Prismic"
        return f"Ingredient_Hide_{t.capitalize()}"
    if canonical_id.startswith("LEATHER:"):
        t = canonical_id.split(":", 1)[1]
        if t == "prism":
            return "Ingredient_Leather_Prismic"
        return f"Ingredient_Leather_{t.capitalize()}"
    if canonical_id.startswith("CLOTH:"):
        t = canonical_id.split(":", 1)[1]
        if t == "shadow_weave":
            return "Ingredient_Fabric_Scrap_Shadoweave"
        if t == "cinder_cloth":
            return "Ingredient_Fabric_Scrap_Cindercloth"
        if t == "linen_scraps":
            return "Ingredient_Fabric_Scrap_Linen"
        return None
    if canonical_id.startswith("CROP:"):
        t = canonical_id.split(":", 1)[1]
        crop_map = {
            "potato": "Plant_Crop_Potato_Item",
            "wheat": "Plant_Crop_Wheat_Item",
            "carrot": "Plant_Crop_Carrot_Item",
            "chili": "Plant_Crop_Chilli_Item",
            "corn": "Plant_Crop_Corn_Item",
            "tomato": "Plant_Crop_Tomato_Item",
            "pumpkin": "Plant_Crop_Pumpkin_Item",
            "turnip": "Plant_Crop_Turnip_Item",
            "onion": "Plant_Crop_Onion_Item",
            "lettuce": "Plant_Crop_Lettuce_Item",
            "rice": "Plant_Crop_Rice_Item",
        }
        return crop_map.get(t)
    if canonical_id == "RESOURCE:wood":
        return "Ingredient_Tree_Bark"
    if canonical_id.startswith("MASS:"):
        t = canonical_id.split(":", 1)[1]
        if t and t != "other":
            if t == "magma":
                return "Rock_Magma_Cooled"
            return f"Rock_{t.capitalize()}"
    return None


def main() -> None:
    policy_path = Path("policies/policy.yml")
    policy = load_policy(policy_path)
    icons = load_icons(Path("data/extracted/item_icons.json"))

    nyra_per_min = float(policy["economy"]["nyra_per_minute"])

    src = Path("data/extracted/canonical_catalog.csv")
    if not src.exists():
        raise SystemExit("Missing data/extracted/canonical_catalog.csv")

    out_dir = Path("data/snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "prices_v0_1.csv"

    rows_out = []

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical_id = row["canonical_id"]
            canonical_kind = row["canonical_kind"]
            profile = row["dominant_profile"]
            zone = int(row["max_zone"])
            rarity = row["rarity_tag"]

            bqty = bundle_for(canonical_kind, canonical_id)
            mpu = minutes_per_unit(profile, canonical_kind, canonical_id)
            if mpu is None and canonical_id != "BASIC:charcoal":
                # skip unpriced entries in v0.1
                continue

            if canonical_id == "BASIC:charcoal":
                bundle_price = 0.10 * bqty
            else:
                # price for ONE unit
                base_unit = mpu * nyra_per_min
                # apply zone + rarity
                final_unit = base_unit * zone_factor(policy, zone) * rarity_factor(
                    policy, rarity
                )
                # bundle price
                bundle_price = final_unit * bqty
            bundle_price = apply_guardrails(
                policy, canonical_id, canonical_kind, bqty, bundle_price
            )

            rows_out.append(
                {
                    "canonical_id": canonical_id,
                    "canonical_kind": canonical_kind,
                    "profile": profile,
                    "zone": zone,
                    "rarity_tag": rarity,
                    "minutes_per_unit": round(mpu, 6),
                    "nyra_per_minute": nyra_per_min,
                    "bundle_qty": bqty,
                    "price_nyra": round(bundle_price, 2),
                    "confidence": "v0.1_fixed" if canonical_id == "BASIC:charcoal" else "v0.1_model",
                    "icon_path": icons.get(canonical_to_item_id(canonical_id) or "", ""),
                }
            )

    # Write
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "canonical_id",
            "canonical_kind",
            "profile",
            "zone",
            "rarity_tag",
            "minutes_per_unit",
            "nyra_per_minute",
            "bundle_qty",
            "price_nyra",
            "confidence",
            "icon_path",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(sorted(rows_out, key=lambda r: r["canonical_id"]))

    print(f"Wrote: {out_path} ({len(rows_out)} priced rows)")


if __name__ == "__main__":
    main()
