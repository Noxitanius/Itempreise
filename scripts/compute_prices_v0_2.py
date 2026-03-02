import csv
import json
from pathlib import Path
import yaml

RARITY_ORDER = ["very_common", "common", "uncommon", "rare", "very_rare", "mythic"]


def load_policy(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_icons(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_recipes(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_recipe_key_map(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def pick_best_recipe_key(recipes: dict, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    # choose recipe with most inputs
    best = None
    best_n = -1
    for k in candidates:
        r = recipes.get(k)
        if not r:
            continue
        n = len(r.get("inputs", []) or [])
        if n > best_n:
            best_n = n
            best = k
    return best or candidates[0]


def rarity_factor(policy: dict, rarity_tag: str) -> float:
    return float(policy["rarity"].get(rarity_tag, 1.0))


def zone_factor(policy: dict, zone: int) -> float:
    return float(policy["zones"][zone]["risk_factor"])


def bundle_for(canonical_kind: str, canonical_id: str) -> int:
    if canonical_kind == "mass":
        return 1000
    if canonical_id.startswith("ORE_MATERIAL:") or canonical_id.startswith("BAR:"):
        return 100
    if canonical_id.startswith("ORE_ITEM:"):
        return 100
    if canonical_id.startswith("CROP:") or canonical_id.startswith("ESSENCE:"):
        return 1000
    return 1


def minutes_per_unit_v01(profile: str, canonical_kind: str, canonical_id: str) -> float | None:
    # price only meaningful groups (we'll expand later)
    if canonical_kind == "mass":
        return 0.002

    if canonical_id.startswith("ORE_MATERIAL:"):
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
        return 0.10

    if canonical_id.startswith("BAR:"):
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
        # v0.2: we still compute raw time but apply damping later
        return 0.012

    if canonical_id.startswith("ESSENCE:"):
        # Essence raw model: tuned later via telemetry, damping applied later
        return 0.0075

    if canonical_kind == "resource":
        return 0.01

    # Basics / Hides / Leather / Cloth (v0.2 defaults)
    if canonical_kind == "basic":
        return 0.01
    if canonical_kind == "hide":
        if profile == "hide_drop_t1":
            return 0.03
        if profile == "hide_drop_t2":
            return 0.05
        if profile == "hide_drop_t3":
            return 0.07
        if profile == "hide_drop_storm":
            return 0.10
        if profile == "hide_drop_prism":
            return 0.15
        return 0.06
    if canonical_kind == "leather":
        return 0.02
    if canonical_kind == "cloth":
        return 0.015
    if canonical_kind == "crystal":
        return 0.04
    if canonical_kind == "gem":
        return 0.05
    if canonical_kind == "potion":
        return 0.02
    if canonical_id == "BASIC:charcoal":
        return 0.0

    return None


def apply_mass_cap(policy: dict, canonical_kind: str, bundle_qty: int, price: float) -> float:
    if canonical_kind != "mass":
        return price
    cap = float(policy["guardrails"].get("mass_goods_cap_nyra_per_1000", 3.0))
    return min(price, cap)


def craft_markup(policy: dict) -> float:
    return float(policy.get("crafting", {}).get("craft_markup", 1.10))


def farm_damp(policy: dict, canonical_id: str) -> float:
    # optional configurable dampening
    fd = policy.get("crafting", {}).get("farm_dampening", None)
    if isinstance(fd, dict):
        if canonical_id.startswith("CROP:"):
            return float(fd.get("crop", 0.35))
        if canonical_id.startswith("ESSENCE:"):
            return float(fd.get("essence", 0.60))
        return 1.0
    # If you did not add farm_dampening block, use hard defaults:
    if canonical_id.startswith("CROP:"):
        return 0.35
    if canonical_id.startswith("ESSENCE:"):
        return 0.60
    return 1.0


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
    if canonical_id == "BASIC:feather_dark":
        return "Ingredient_Feathers_Dark"
    if canonical_id == "BASIC:boom_powder":
        return "Ingredient_Powder_Boom"
    if canonical_id == "BASIC:venom_sac":
        return "Ingredient_Sac_Venom"
    if canonical_id == "BASIC:voidheart":
        return "Ingredient_Voidheart"
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
        if t == "cotton":
            return "Ingredient_Bolt_Cotton"
        if t == "silk":
            return "Ingredient_Bolt_Silk"
        if t == "wool":
            return "Ingredient_Bolt_Wool"
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
            "berry": "Plant_Fruit_Berries_Red",
        }
        return crop_map.get(t)
    if canonical_id.startswith("POTION:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id == "RESOURCE:wood":
        return "Ingredient_Tree_Bark"
    if canonical_id.startswith("POTION:"):
        return canonical_id.split(":", 1)[1]
    if canonical_id.startswith("MASS:"):
        t = canonical_id.split(":", 1)[1]
        if t and t != "other":
            if t == "magma":
                return "Rock_Magma_Cooled"
            return f"Rock_{t.capitalize()}"
    return None


def recipe_key_candidates(canonical_id: str) -> list[str]:
    # Map canonical ids to likely recipe keys (filename stems)
    # BAR:prisma -> Ingredient_Bar_Prisma
    if canonical_id.startswith("BAR:"):
        mat = canonical_id.split(":", 1)[1]
        return [f"Ingredient_Bar_{mat.capitalize()}", f"Ingredient_Bar_{mat.upper()}"]
    if canonical_id.startswith("ARMOR:"):
        return [canonical_id.split(":", 1)[1]]
    if canonical_id.startswith("WEAPON:"):
        return [canonical_id.split(":", 1)[1]]
    if canonical_id.startswith("TOOL:"):
        return [canonical_id.split(":", 1)[1]]
    if canonical_id.startswith("CLOTH:"):
        t = canonical_id.split(":", 1)[1]
        if t == "cotton":
            return ["Ingredient_Bolt_Cotton"]
        if t == "silk":
            return ["Ingredient_Bolt_Silk"]
        if t == "wool":
            return ["Ingredient_Bolt_Wool"]
        if t == "linen_scraps":
            return ["Ingredient_Fabric_Scrap_Linen"]
        if t == "shadow_weave":
            return ["Ingredient_Fabric_Scrap_Shadoweave"]
        if t == "cinder_cloth":
            return ["Ingredient_Fabric_Scrap_Cindercloth"]
    # If later we support direct ore items as crafts:
    if canonical_id.startswith("ORE_ITEM:"):
        x = canonical_id.split(":", 1)[1]
        return [x]
    return []


def canonical_for_input(inp: dict) -> str | None:
    # Convert recipe inputs to canonical keys we can price against.
    t = inp["type"]
    iid = inp["id"]
    if t == "item":
        s = iid.lower()
        if s.startswith("ingredient_stick"):
            return "BASIC:stick"
        if s.startswith("ingredient_charcoal"):
            return "BASIC:charcoal"
        if s.startswith("ingredient_fibre") or s.startswith("ingredient_fiber"):
            return "BASIC:plant_fiber"
        if s.startswith("ingredient_tree_sap"):
            return "BASIC:tree_sap"
        if s.startswith("ingredient_feather") or s.startswith("ingredient_feathers"):
            return "BASIC:feather_dark"
        if s.startswith("ingredient_powder_boom"):
            return "BASIC:boom_powder"
        if s.startswith("ingredient_sac_venom"):
            return "BASIC:venom_sac"
        if s.startswith("ingredient_voidheart"):
            return "BASIC:voidheart"
        if s.startswith("ingredient_hide"):
            if "prism" in s or "prisma" in s:
                return "HIDE:prism"
            for t in ["storm", "heavy", "medium", "light"]:
                if t in s:
                    return f"HIDE:{t}"
            return "HIDE:generic"
        if s.startswith("ingredient_leather"):
            if "prism" in s or "prisma" in s:
                return "LEATHER:prism"
            for t in ["storm", "heavy", "medium", "light"]:
                if t in s:
                    return f"LEATHER:{t}"
            return "LEATHER:generic"
        if "fabric_scrap" in s or "ingredient_fabric_scrap" in s:
            if "shadow" in s:
                return "CLOTH:shadow_weave"
            if "cinder" in s:
                return "CLOTH:cinder_cloth"
            if "linen" in s:
                return "CLOTH:linen_scraps"
            return "CLOTH:scraps"
        if "ingredient_bolt" in s and ("linen" in s or "shadow" in s or "cinder" in s):
            if "shadow" in s:
                return "CLOTH:shadow_weave"
            if "cinder" in s:
                return "CLOTH:cinder_cloth"
            if "linen" in s:
                return "CLOTH:linen_scraps"
            return "CLOTH:bolt"
        if "ingredient_bolt" in s and ("cotton" in s or "silk" in s or "wool" in s):
            if "cotton" in s:
                return "CLOTH:cotton"
            if "silk" in s:
                return "CLOTH:silk"
            if "wool" in s:
                return "CLOTH:wool"
            return "CLOTH:bolt"
        if s.startswith("ingredient_crystal_"):
            t = s.replace("ingredient_crystal_", "")
            return f"CRYSTAL:{t}"
        if s.startswith("rock_gem_") or "rock_gem_" in s:
            t = s.replace("rock_gem_", "")
            return f"GEM:{t}"
        if s.startswith("ingredient_bar_"):
            mat = s.replace("ingredient_bar_", "")
            return f"BAR:{mat}"
        if s.startswith("rock_") or s.startswith("rubble_"):
            return "MASS:stone"
        if s.startswith("ore_"):
            # Map vanilla ores to ORE_MATERIAL, endgame ores to ORE_ITEM
            if "onyxium" in s or "mithril" in s:
                return f"ORE_ITEM:{iid}"
            for mat in [
                "copper",
                "iron",
                "thorium",
                "cobalt",
                "silver",
                "gold",
                "adamantite",
                "bronze",
                "steel",
            ]:
                if mat in s:
                    return f"ORE_MATERIAL:{mat}"
            return f"ORE_ITEM:{iid}"
        if s.startswith("plant_fruit_berries"):
            return "CROP:berry"
        if s.startswith("potion_") or "potion_" in s:
            return f"POTION:{iid}"
        if "essence" in s:
            return "ESSENCE:life"
        # fallback: treat as raw item
        return None
    elif t == "resource":
        rs = iid.lower()
        if rs in ("rock", "rubble"):
            return "MASS:stone"
        if rs in ("wood_all", "wood_trunk", "wood"):
            return "RESOURCE:wood"
        if rs.startswith("resource_wood_"):
            return "RESOURCE:wood"
        return f"RESOURCE:{iid}"
    return None


def main() -> None:
    policy = load_policy(Path("policies/policy.yml"))
    icons = load_icons(Path("data/extracted/item_icons.json"))
    recipes = load_recipes(Path("data/extracted/recipes.json"))
    recipe_key_map = load_recipe_key_map(Path("data/extracted/recipe_key_map.json"))

    nyra_per_min = float(policy["economy"]["nyra_per_minute"])

    src = Path("data/extracted/canonical_catalog.csv")
    if not src.exists():
        raise SystemExit("Missing data/extracted/canonical_catalog.csv")

    out_dir = Path("data/snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "prices_v0_2.csv"

    # First pass: compute v0.1-like prices for canonical ids we know how to model
    base_prices = {}  # canonical_id -> (bundle_qty, price_nyra, meta)
    rows_by_id = {}

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical_id = row["canonical_id"]
            canonical_kind = row["canonical_kind"]
            profile = row["dominant_profile"]
            zone = int(row["max_zone"])
            rarity = row["rarity_tag"]

            rows_by_id[canonical_id] = row
            bqty = bundle_for(canonical_kind, canonical_id)
            mpu = minutes_per_unit_v01(profile, canonical_kind, canonical_id)

            if mpu is None and canonical_id != "BASIC:charcoal":
                continue

            if canonical_id == "BASIC:charcoal":
                bundle_price = 0.10 * bqty
            else:
                base_unit = mpu * nyra_per_min
                final_unit = base_unit * zone_factor(policy, zone) * rarity_factor(
                    policy, rarity
                )
                bundle_price = final_unit * bqty

            # apply mass cap
            bundle_price = apply_mass_cap(policy, canonical_kind, bqty, bundle_price)

            # apply farm dampening
            bundle_price *= farm_damp(policy, canonical_id)

            meta = {
                "canonical_kind": canonical_kind,
                "profile": profile,
                "zone": zone,
                "rarity_tag": rarity,
                "minutes_per_unit": mpu,
                "calc": "fixed" if canonical_id == "BASIC:charcoal" else "model",
                "icon_path": icons.get(canonical_to_item_id(canonical_id) or "", ""),
            }
            base_prices[canonical_id] = (bqty, bundle_price, meta)

    # Helper: get unit price from bundle price
    def unit_price(canonical_id: str) -> float | None:
        # direct known prices
        if canonical_id in base_prices:
            bqty, bprice, _ = base_prices[canonical_id]
            return bprice / bqty if bqty else None

        return None

    # Second pass: BOM pricing for craftable entries (BAR, LEATHER, CLOTH, etc.)
    # Iterate until stable (or max passes) to resolve long dependency chains.
    max_passes = 20
    for _ in range(max_passes):
        overrides = {}
        for canonical_id in list(rows_by_id.keys()):
            # find recipe by candidate keys
            candidates = recipe_key_map.get(canonical_id, [])
            if not candidates:
                candidates = recipe_key_candidates(canonical_id)
            rk = pick_best_recipe_key(recipes, candidates)
            inputs = []
            out_qty = 1
            synth_recipe_key = ""
            if rk is not None and rk in recipes:
                recipe = recipes[rk]
                inputs = list(recipe.get("inputs", []))
                out_qty = int(recipe.get("output_qty", 1) or 1)
                if rk == "Ingredient_Bar_Mithril":
                    # add furnace fuel (charcoal)
                    inputs.append(
                        {"type": "item", "id": "Ingredient_Charcoal", "qty": 1}
                    )
            elif canonical_id.startswith("BAR:"):
                # Fallback: vanilla ore -> bar processing (recipe files not present)
                mat = canonical_id.split(":", 1)[1]
                synth_recipe_key = f"SYNTH:ORE_MATERIAL:{mat}"
                # Use canonical ore material directly
                inputs = [{"type": "canonical", "id": f"ORE_MATERIAL:{mat}", "qty": 1}]
                out_qty = 1
            else:
                continue

            if not inputs:
                continue

            total_cost_per_unit = 0.0
            missing = []

            for inp in inputs:
                if inp.get("type") == "canonical":
                    c_in = inp["id"]
                else:
                    c_in = canonical_for_input(inp)
                qty = float(inp["qty"])
                if c_in is None:
                    missing.append(inp["id"])
                    continue

                if c_in.startswith("ORE_ITEM:"):
                    ore_id = c_in.split(":", 1)[1]
                    p = unit_price(f"ORE_ITEM:{ore_id}")
                    if p is None:
                        missing.append(ore_id)
                        continue
                    total_cost_per_unit += p * qty
                    continue

                p = unit_price(c_in)
                if p is None:
                    missing.append(c_in)
                    continue

                total_cost_per_unit += p * qty

            if total_cost_per_unit <= 0:
                continue

            # Normalize by output quantity
            if out_qty > 1:
                total_cost_per_unit = total_cost_per_unit / out_qty

            # Craft markup
            total_cost_per_unit *= craft_markup(policy)

            # Convert to bundle price
            if canonical_id in base_prices:
                bqty, _, meta = base_prices[canonical_id]
            else:
                row = rows_by_id[canonical_id]
                bqty = bundle_for(row["canonical_kind"], canonical_id)
                meta = {
                    "canonical_kind": row["canonical_kind"],
                    "profile": row["dominant_profile"],
                    "zone": int(row["max_zone"]),
                    "rarity_tag": row["rarity_tag"],
                    "minutes_per_unit": "",
                    "calc": "bom",
                    "icon_path": icons.get(canonical_to_item_id(canonical_id) or "", ""),
                }
            new_bundle = total_cost_per_unit * bqty

            bom_meta = {
                **meta,
                "calc": "bom",
                "recipe_key": rk or synth_recipe_key,
                "missing_inputs": "|".join(missing) if missing else "",
            }
            if "icon_path" not in bom_meta:
                bom_meta["icon_path"] = icons.get(
                    canonical_to_item_id(canonical_id) or "", ""
                )
            overrides[canonical_id] = (
                bqty,
                new_bundle,
                bom_meta,
            )

        if not overrides:
            break
        for k, v in overrides.items():
            base_prices[k] = v

    # Write snapshot
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "canonical_id",
            "canonical_kind",
            "profile",
            "zone",
            "rarity_tag",
            "bundle_qty",
            "price_nyra",
            "calc",
            "recipe_key",
            "missing_inputs",
            "icon_path",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for canonical_id in sorted(base_prices.keys()):
            bqty, price, meta = base_prices[canonical_id]
            w.writerow(
                {
                    "canonical_id": canonical_id,
                    "canonical_kind": meta["canonical_kind"],
                    "profile": meta["profile"],
                    "zone": meta["zone"],
                    "rarity_tag": meta["rarity_tag"],
                    "bundle_qty": bqty,
                    "price_nyra": round(price, 2),
                    "calc": meta.get("calc", "model"),
                    "recipe_key": meta.get("recipe_key", ""),
                    "missing_inputs": meta.get("missing_inputs", ""),
                    "icon_path": meta.get("icon_path", ""),
                }
            )

    print(
        f"Wrote: {out_path} (priced {len(base_prices)} rows, bom overrides {len(overrides)})"
    )


if __name__ == "__main__":
    main()
