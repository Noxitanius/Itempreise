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

    # Bars (prefer furnace recipe, fallback to Ingredient_Bar_*)
    def bar_recipe_key(mat: str):
        return (
            find_key_startswith(f"Recipe_Bar_{mat}_Furnace")
            or find_key_startswith(f"Recipe_Bar_{mat}")
            or find_key_startswith(f"Ingredient_Bar_{mat}")
        )

    mapping["BAR:prisma"] = bar_recipe_key("Prisma")
    mapping["BAR:onyxium"] = bar_recipe_key("Onyxium")
    mapping["BAR:mithril"] = bar_recipe_key("Mithril")
    mapping["BAR:adamantite"] = bar_recipe_key("Adamantite")
    mapping["BAR:cobalt"] = bar_recipe_key("Cobalt")
    mapping["BAR:thorium"] = bar_recipe_key("Thorium")
    mapping["BAR:iron"] = bar_recipe_key("Iron")
    mapping["BAR:copper"] = bar_recipe_key("Copper")
    mapping["BAR:silver"] = bar_recipe_key("Silver")
    mapping["BAR:gold"] = bar_recipe_key("Gold")
    mapping["BAR:bronze"] = bar_recipe_key("Bronze")
    mapping["BAR:steel"] = bar_recipe_key("Steel")

    # Ore items (craft/boss) – optional
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
    mapping["CLOTH:cotton"] = find_key_startswith("Ingredient_Bolt_Cotton")
    mapping["CLOTH:silk"] = find_key_startswith("Ingredient_Bolt_Silk")
    mapping["CLOTH:wool"] = find_key_startswith("Ingredient_Bolt_Wool")

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
