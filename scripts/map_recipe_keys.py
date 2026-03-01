import json
from pathlib import Path


def main() -> None:
    recipes_path = Path("data/extracted/recipes.json")
    recipes = json.loads(recipes_path.read_text(encoding="utf-8"))

    # find likely keys by contains-match (case-insensitive)
    def find_key_contains(*needles: str, exclude_prefixes: tuple[str, ...] = ()):
        needles_l = [n.lower() for n in needles]
        hits = []
        for k in recipes.keys():
            kl = k.lower()
            if exclude_prefixes and any(kl.startswith(p) for p in exclude_prefixes):
                continue
            if all(n in kl for n in needles_l):
                hits.append(k)
        return sorted(hits)

    # prefer explicit prefix matches (case-insensitive)
    def find_key_startswith(prefix: str):
        pref = prefix.lower()
        hits = []
        for k in recipes.keys():
            if k.lower().startswith(pref):
                hits.append(k)
        return sorted(hits)

    mapping = {}

    # Bars (only Ingredient_Bar_* recipes)
    mapping["BAR:prisma"] = find_key_startswith("Ingredient_Bar_Prisma")
    mapping["BAR:onyxium"] = find_key_startswith("Ingredient_Bar_Onyxium")
    mapping["BAR:mithril"] = find_key_startswith("Ingredient_Bar_Mithril")

    # Ore items (craft/boss) – optional
    mapping["ORE_ITEM:Ore_Prisma"] = find_key_contains("ore", "prisma")
    mapping["ORE_ITEM:Ore_Onyxium"] = find_key_contains("ore", "onyxium")
    mapping["ORE_ITEM:Ore_Mithril"] = find_key_contains("ore", "mithril")

    # Leather (only Ingredient_Leather_* recipes)
    mapping["LEATHER:light"] = find_key_startswith("Ingredient_Leather_Light")
    mapping["LEATHER:medium"] = find_key_startswith("Ingredient_Leather_Medium")
    mapping["LEATHER:heavy"] = find_key_startswith("Ingredient_Leather_Heavy")
    mapping["LEATHER:storm"] = find_key_startswith("Ingredient_Leather_Storm")
    mapping["LEATHER:prism"] = find_key_startswith("Ingredient_Leather_Prismic")

    # Cloth scraps
    mapping["CLOTH:linen_scraps"] = find_key_contains("fabric", "scrap", "linen")
    mapping["CLOTH:shadow_weave"] = find_key_contains("fabric", "scrap", "shadow")
    mapping["CLOTH:cinder_cloth"] = find_key_contains("fabric", "scrap", "cinder")

    out = Path("data/extracted/recipe_key_map.json")
    out.write_text(json.dumps(mapping, indent=2), encoding="utf-8")
    print(f"Wrote {out}")

    # Quick print for you
    for k, v in mapping.items():
        print(f"{k}: {len(v)} candidates")
        for cand in v[:10]:
            print(f"  - {cand}")
        if len(v) > 10:
            print("  ...")


if __name__ == "__main__":
    main()
