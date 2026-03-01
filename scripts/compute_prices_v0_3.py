import csv
import json
from pathlib import Path
import yaml

RARITY_ORDER = ["very_common", "common", "uncommon", "rare", "very_rare", "mythic"]


def load_policy(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_recipes(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_profile_minutes(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_recipe_key_map(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_overrides(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] Failed to load overrides: {path} ({e})")
        return {}


def pick_best_recipe_key(recipes: dict, candidates: list[str]) -> str | None:
    if not candidates:
        return None
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


def minutes_per_unit(
    profile: str,
    canonical_kind: str,
    canonical_id: str,
    profile_minutes: dict,
) -> float | None:
    # 1) If telemetry has the profile, use it.
    if profile in profile_minutes:
        return float(profile_minutes[profile])

    # 2) Fallback defaults (v0.2-style)
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
        return 0.012
    if canonical_id.startswith("ESSENCE:"):
        return 0.0075
    if canonical_kind == "resource":
        return 0.01
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
    return None


def apply_mass_cap(policy: dict, canonical_kind: str, price: float) -> float:
    if canonical_kind != "mass":
        return price
    cap = float(policy["guardrails"].get("mass_goods_cap_nyra_per_1000", 3.0))
    return min(price, cap)


def boss_floor(policy: dict, canonical_id: str) -> float | None:
    floors = policy.get("boss_drops", {}).get("floor_by_item", {})
    return float(floors[canonical_id]) if canonical_id in floors else None


def craft_markup(policy: dict) -> float:
    return float(policy.get("crafting", {}).get("craft_markup", 1.10))


def farm_damp(policy: dict, canonical_id: str) -> float:
    fd = policy.get("crafting", {}).get("farm_dampening", None)
    if isinstance(fd, dict):
        if canonical_id.startswith("CROP:"):
            return float(fd.get("crop", 0.35))
        if canonical_id.startswith("ESSENCE:"):
            return float(fd.get("essence", 0.60))
        return 1.0
    if canonical_id.startswith("CROP:"):
        return 0.35
    if canonical_id.startswith("ESSENCE:"):
        return 0.60
    return 1.0


def canonical_for_input(inp: dict) -> str | None:
    t = inp["type"]
    iid = inp["id"]
    if t == "item":
        s = iid.lower()
        if s.startswith("ingredient_stick"):
            return "BASIC:stick"
        if s.startswith("ingredient_fibre") or s.startswith("ingredient_fiber"):
            return "BASIC:plant_fiber"
        if s.startswith("ingredient_tree_sap"):
            return "BASIC:tree_sap"
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
        if s.startswith("ingredient_bar_"):
            mat = s.replace("ingredient_bar_", "")
            return f"BAR:{mat}"
        if s.startswith("ore_"):
            return f"ORE_ITEM:{iid}"
        if "essence" in s:
            types = ["life", "void", "fire", "water", "ice", "earth", "air", "storm"]
            for et in types:
                if et in s:
                    return f"ESSENCE:{et}"
            return "ESSENCE:generic"
        return None
    if t == "resource":
        return f"RESOURCE:{iid}"
    return None


def apply_override(canonical_id: str, bundle_qty: int, bundle_price: float, meta: dict, ovr_cfg: dict) -> tuple[float, dict]:
    ov = ovr_cfg.get(canonical_id)
    if not ov:
        return bundle_price, meta

    def add_calc(tag: str) -> None:
        meta["calc"] = (meta.get("calc", "") + f"|{tag}").strip("|")

    if ov.get("price_nyra") is not None:
        bundle_price = float(ov["price_nyra"])
        add_calc("override_price")

    if ov.get("floor_nyra") is not None:
        bundle_price = max(bundle_price, float(ov["floor_nyra"]))
        add_calc("override_floor")

    if ov.get("ceil_nyra") is not None:
        bundle_price = min(bundle_price, float(ov["ceil_nyra"]))
        add_calc("override_ceil")

    if ov.get("disable_bom") is True:
        meta["disable_bom"] = True
        add_calc("disable_bom")

    if ov.get("note"):
        meta["override_note"] = str(ov["note"])

    return bundle_price, meta


def main() -> None:
    policy = load_policy(Path("policies/policy.yml"))
    recipes = load_recipes(Path("data/extracted/recipes.json"))
    recipe_key_map = load_recipe_key_map(Path("data/extracted/recipe_key_map.json"))
    profile_minutes = load_profile_minutes(Path("data/extracted/profile_minutes_v0_3.json"))
    ovr_cfg = load_overrides(Path("data/overrides/overrides.json"))

    nyra_per_min = float(policy["economy"]["nyra_per_minute"])

    src = Path("data/extracted/canonical_catalog.csv")
    if not src.exists():
        raise SystemExit("Missing data/extracted/canonical_catalog.csv")

    out_dir = Path("data/snapshots")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "prices_v0_3.csv"

    base_prices = {}  # canonical_id -> (bundle_qty, price_nyra, meta)

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            canonical_id = row["canonical_id"]
            canonical_kind = row["canonical_kind"]
            profile = row["dominant_profile"]
            zone = int(row["max_zone"])
            rarity = row["rarity_tag"]

            bqty = bundle_for(canonical_kind, canonical_id)
            mpu = minutes_per_unit(profile, canonical_kind, canonical_id, profile_minutes)
            if mpu is None:
                continue

            base_unit = mpu * nyra_per_min
            final_unit = base_unit * zone_factor(policy, zone) * rarity_factor(policy, rarity)
            bundle_price = final_unit * bqty

            bundle_price = apply_mass_cap(policy, canonical_kind, bundle_price)
            bundle_price *= farm_damp(policy, canonical_id)

            floor = boss_floor(policy, canonical_id)
            if floor is not None:
                bundle_price = max(bundle_price, floor)

            meta = {
                "canonical_kind": canonical_kind,
                "profile": profile,
                "zone": zone,
                "rarity_tag": rarity,
                "minutes_per_unit": mpu,
                "calc": "model_v0.3",
            }
            bundle_price, meta = apply_override(canonical_id, bqty, bundle_price, meta, ovr_cfg)
            base_prices[canonical_id] = (bqty, bundle_price, meta)

    def unit_price(canonical_id: str) -> float | None:
        if canonical_id in base_prices:
            bqty, bprice, _ = base_prices[canonical_id]
            return bprice / bqty if bqty else None
        floor = boss_floor(policy, canonical_id)
        if floor is not None:
            bqty = bundle_for("", canonical_id)
            return floor / bqty if bqty else floor
        return None

    # BOM overrides
    bom_overrides = {}
    for canonical_id in list(base_prices.keys()):
        if ovr_cfg.get(canonical_id, {}).get("disable_bom") is True:
            continue
        candidates = recipe_key_map.get(canonical_id, [])
        rk = pick_best_recipe_key(recipes, candidates)
        if rk is None:
            continue
        recipe = recipes[rk]
        inputs = recipe.get("inputs", [])
        if not inputs:
            continue

        total_cost_per_unit = 0.0
        missing = []

        for inp in inputs:
            c_in = canonical_for_input(inp)
            qty = float(inp["qty"])
            if c_in is None:
                missing.append(inp["id"])
                continue
            if c_in.startswith("ORE_ITEM:"):
                ore_id = c_in.split(":", 1)[1]
                p = unit_price(f"ORE_ITEM:{ore_id}")
                if p is None:
                    floor = boss_floor(policy, f"ORE_ITEM:{ore_id}")
                    if floor is not None:
                        p = floor
                    else:
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

        total_cost_per_unit *= craft_markup(policy)
        bqty, _, meta = base_prices[canonical_id]
        new_bundle = total_cost_per_unit * bqty

        floor = boss_floor(policy, canonical_id)
        if floor is not None:
            new_bundle = max(new_bundle, floor)

        new_meta = {
            **meta,
            "calc": "bom_v0.3",
            "recipe_key": rk,
            "missing_inputs": "|".join(missing) if missing else "",
        }
        new_bundle, new_meta = apply_override(canonical_id, bqty, new_bundle, new_meta, ovr_cfg)
        bom_overrides[canonical_id] = (bqty, new_bundle, new_meta)

    for k, v in bom_overrides.items():
        base_prices[k] = v

    # Virtual floor-only entries for boss-drop ore items
    virtual_ids = ["ORE_ITEM:Ore_Prisma", "ORE_ITEM:Ore_Onyxium"]
    for vid in virtual_ids:
        if vid in base_prices:
            continue
        floor = boss_floor(policy, vid)
        if floor is None:
            continue
        bqty = bundle_for("raw", vid)
        price = floor
        meta = {
            "canonical_kind": "boss_drop_ore",
            "profile": "boss_floor",
            "zone": 4,
            "rarity_tag": "mythic",
            "calc": "floor_v0.3",
            "recipe_key": "",
            "missing_inputs": "",
            "minutes_per_unit": "",
        }
        price, meta = apply_override(vid, bqty, price, meta, ovr_cfg)
        base_prices[vid] = (bqty, price, meta)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "canonical_id",
            "canonical_kind",
            "profile",
            "zone",
            "rarity_tag",
            "minutes_per_unit",
            "bundle_qty",
            "price_nyra",
            "calc",
            "recipe_key",
            "missing_inputs",
            "override_note",
        ]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for canonical_id in sorted(base_prices.keys()):
            bqty, price, meta = base_prices[canonical_id]
            w.writerow(
                {
                    "canonical_id": canonical_id,
                    "canonical_kind": meta["canonical_kind"],
                    "profile": meta.get("profile", ""),
                    "zone": meta.get("zone", ""),
                    "rarity_tag": meta.get("rarity_tag", ""),
                    "minutes_per_unit": meta.get("minutes_per_unit", ""),
                    "bundle_qty": bqty,
                    "price_nyra": round(price, 2),
                    "calc": meta.get("calc", ""),
                    "recipe_key": meta.get("recipe_key", ""),
                    "missing_inputs": meta.get("missing_inputs", ""),
                    "override_note": meta.get("override_note", ""),
                }
            )

    print(
        f"Wrote: {out_path} (priced {len(base_prices)} rows, bom overrides {len(bom_overrides)})"
    )


if __name__ == "__main__":
    main()
