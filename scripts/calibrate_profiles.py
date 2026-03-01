import csv
import json
from collections import defaultdict
from pathlib import Path

ORE_MATERIAL_MAP = {
    # map ore item ids to profile tier buckets (adjust as needed)
    "ore_copper": "ore_t1",
    "ore_iron": "ore_t1",
    "ore_thorium": "ore_t2",
    "ore_silver": "ore_t2",
    "ore_cobalt": "ore_t3",
    "ore_gold": "ore_t3",
    "ore_adamantite": "ore_t4",
    "ore_mithril": "endgame_mithril",
}


def norm(s: str) -> str:
    return s.strip().lower()


def classify_observation(item_id: str) -> str | None:
    s = norm(item_id)

    # canonical already
    if s.startswith("crop:"):
        return "crop"
    if s.startswith("essence:"):
        return "essence_life" if "life" in s else "essence_generic"
    if s.startswith("ore_item:"):
        return "boss_drop_ore"

    # typical ore ids
    for k, prof in ORE_MATERIAL_MAP.items():
        if k in s:
            return prof

    # allow "Ore_Cobalt" etc
    if s.startswith("ore_"):
        # best effort: find material token after ore_
        for k, prof in ORE_MATERIAL_MAP.items():
            if k in s:
                return prof

    return None


def main() -> None:
    src = Path("data/telemetry/telemetry_runs.csv")
    if not src.exists():
        # allow using the template as starting point
        src = Path("data/telemetry/telemetry_template.csv")
        if not src.exists():
            raise SystemExit("Missing telemetry_runs.csv (or telemetry_template.csv)")

    # accumulate per profile: total effective minutes / total units
    minutes_sum = defaultdict(float)
    units_sum = defaultdict(float)

    # also capture zone efficiency stats (optional)
    zone_minutes = defaultdict(float)
    zone_units = defaultdict(float)

    # group rows by run_id to compute effective duration once
    runs = {}
    rows_by_run = defaultdict(list)

    with src.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            run_id = row["run_id"].strip()
            run_type = row["run_type"].strip()
            zone = int(row["zone"])
            dur = float(row["duration_minutes"])
            lost = float(row.get("time_lost_minutes", "0") or 0)
            item_id = row["item_id"].strip()
            qty = float(row["quantity"] or 0)

            runs[run_id] = {
                "run_type": run_type,
                "zone": zone,
                "duration": dur,
                "lost": lost,
            }
            rows_by_run[run_id].append((item_id, qty))

    for run_id, meta in runs.items():
        eff_minutes = max(0.0, meta["duration"] + meta["lost"])
        obs = rows_by_run[run_id]

        # Distribute full effective time across each observed profile separately,
        # but only if the run is "focused" (mine/farm/boss).
        # For a mining run, we assume the whole run time produced the observed ores.
        for item_id, qty in obs:
            if qty <= 0:
                continue
            prof = classify_observation(item_id)
            if not prof:
                continue

            minutes_sum[prof] += eff_minutes
            units_sum[prof] += qty

            zone_minutes[meta["zone"]] += eff_minutes
            zone_units[meta["zone"]] += qty

    # compute minutes per unit
    mpu = {}
    for prof in sorted(minutes_sum.keys()):
        if units_sum[prof] > 0:
            mpu[prof] = minutes_sum[prof] / units_sum[prof]

    out_dir = Path("data/extracted")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "profile_minutes_v0_3.json"
    out_path.write_text(json.dumps(mpu, indent=2), encoding="utf-8")

    print(f"Wrote {out_path}")
    print("Minutes per unit (sample):")
    for k, v in sorted(mpu.items(), key=lambda kv: kv[0]):
        print(f"  {k}: {v:.6f} min/unit")

    # optional zone efficiency info
    print("\nZone efficiency (units per minute, raw):")
    for z in sorted(zone_minutes.keys()):
        m = zone_minutes[z]
        u = zone_units[z]
        if m > 0:
            print(f"  Zone {z}: {u/m:.3f} units/min (across tracked outputs)")


if __name__ == "__main__":
    main()
