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

    mapping = {}

    # Bars
    mapping["BAR:prisma"] = find_key_contains("bar", "prisma")
    mapping["BAR:onyxium"] = find_key_contains("bar", "onyxium")

    # Ore items (craft/boss) – optional
    mapping["ORE_ITEM:Ore_Prisma"] = find_key_contains("ore", "prisma")
    mapping["ORE_ITEM:Ore_Onyxium"] = find_key_contains("ore", "onyxium")

    # Leather (prefer Ingredient_Leather_* recipes; exclude Armor_ to avoid gear recipes)
    mapping["LEATHER:light"] = find_key_contains("ingredient", "leather", "light", exclude_prefixes=("armor_",))
    mapping["LEATHER:medium"] = find_key_contains("ingredient", "leather", "medium", exclude_prefixes=("armor_",))
    mapping["LEATHER:heavy"] = find_key_contains("ingredient", "leather", "heavy", exclude_prefixes=("armor_",))
    mapping["LEATHER:storm"] = find_key_contains("ingredient", "leather", "storm", exclude_prefixes=("armor_",))
    mapping["LEATHER:prism"] = find_key_contains("ingredient", "leather", "prism", exclude_prefixes=("armor_",))

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
