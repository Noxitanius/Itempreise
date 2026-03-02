import json
import shutil
from pathlib import Path


def main() -> None:
    icons_path = Path("data/extracted/item_icons.json")
    if not icons_path.exists():
        raise SystemExit("Missing data/extracted/item_icons.json. Run extract_icons.py first.")

    icon_map = json.loads(icons_path.read_text(encoding="utf-8"))
    icon_paths = sorted({p for p in icon_map.values() if isinstance(p, str) and p.endswith(".png")})

    # Candidate roots in raw data
    roots = [
        Path("data/raw/Assets/Common"),
        Path("data/raw/Assets/Client"),
        Path("data/raw/Assets"),
    ]

    out_root = Path("ui/public")
    copied = 0
    missing = []

    for rel in icon_paths:
        rel_path = Path(rel.replace("\\", "/"))
        src = None
        for r in roots:
            cand = r / rel_path
            if cand.exists():
                src = cand
                break
        if not src:
            missing.append(rel)
            continue

        dst = out_root / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        copied += 1

    print(f"Copied {copied} icons to {out_root}")
    if missing:
        print(f"Missing {len(missing)} icons (first 10):")
        for m in missing[:10]:
            print(f"  - {m}")


if __name__ == "__main__":
    main()
