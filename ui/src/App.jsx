import React, { useEffect, useMemo, useState } from "react";
import "./App.css";
import logo from "./assets/logo.png";

// ---- tiny CSV parser (good enough for our snapshots) ----
function parseCSV(text) {
  const lines = text.replace(/\r/g, "").split("\n").filter(Boolean);
  if (lines.length === 0) return [];
  const header = splitCSVLine(lines[0]);
  return lines.slice(1).map((line) => {
    const cols = splitCSVLine(line);
    const row = {};
    header.forEach((h, i) => (row[h] = cols[i] ?? ""));
    return row;
  });
}

function splitCSVLine(line) {
  const out = [];
  let cur = "";
  let inQ = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"' && line[i + 1] === '"') {
      cur += '"';
      i++;
      continue;
    }
    if (c === '"') {
      inQ = !inQ;
      continue;
    }
    if (c === "," && !inQ) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += c;
  }
  out.push(cur);
  return out;
}

function toCSV(rows, headers) {
  const esc = (v) => {
    const s = String(v ?? "");
    if (s.includes('"') || s.includes(",") || s.includes("\n")) {
      return `"${s.replaceAll('"', '""')}"`;
    }
    return s;
  };
  const out = [];
  out.push(headers.join(","));
  for (const r of rows) {
    out.push(headers.map((h) => esc(r[h])).join(","));
  }
  return out.join("\n");
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

function num(x) {
  const v = Number(x);
  return Number.isFinite(v) ? v : null;
}

function badge(text) {
  return (
    <span
      style={{
        padding: "2px 8px",
        borderRadius: 999,
          border: "1px solid rgba(76, 180, 170, 0.25)",
        fontSize: 12,
        opacity: 0.9,
        marginRight: 6,
        display: "inline-block",
      }}
    >
      {text}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>{title}</div>
      {children}
    </div>
  );
}

async function loadJSONFile(file) {
  const text = await file.text();
  return JSON.parse(text);
}

function baseUrl() {
  try {
    // Vite injects BASE_URL at build time
    return import.meta?.env?.BASE_URL ?? "/";
  } catch {
    return "/";
  }
}

async function loadJSONFromUrl(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  return res.json();
}

async function loadCSVFromUrl(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load ${url}`);
  const text = await res.text();
  return parseCSV(text);
}

function toCanonicalFromRecipeInput(inp) {
  const t = inp.type;
  const id = inp.id;
  const s = String(id).toLowerCase();

  if (t === "item") {
    return id;
  }

  if (t === "resource") {
    return id;
  }
  return null;
}

export default function App() {
  const [pricesA, setPricesA] = useState(null); // v0.1
  const [pricesB, setPricesB] = useState(null); // v0.2
  const [recipes, setRecipes] = useState(null);
  const [recipeKeyMap, setRecipeKeyMap] = useState(null);
  const [iconBaseUrl, setIconBaseUrl] = useState(
    () => localStorage.getItem("nyrell_icon_base") || ""
  );
  const [overrides, setOverrides] = useState(null); // { name, obj }
  const [overrideDraft, setOverrideDraft] = useState({
    price_nyra: "",
    floor_nyra: "",
    ceil_nyra: "",
    disable_bom: false,
    note: "",
  });

  function normalizeOverridesPayload(obj) {
    if (!obj || typeof obj !== "object") return { meta: {}, overrides: {} };
    if (obj.overrides && typeof obj.overrides === "object") {
      return { meta: obj.meta ?? {}, overrides: obj.overrides };
    }
    return { meta: {}, overrides: obj };
  }

  const overridesPayload = useMemo(
    () => normalizeOverridesPayload(overrides?.obj),
    [overrides]
  );
  const overridesMap = overridesPayload.overrides;

  const [selectedId, setSelectedId] = useState(null);

  const [search, setSearch] = useState("");
  const [filterZone, setFilterZone] = useState("all");
  const [filterRarity, setFilterRarity] = useState("all");
  const [filterCalc, setFilterCalc] = useState("all");
  const [filterKind, setFilterKind] = useState("all");
  const [onlyChanged, setOnlyChanged] = useState(false);

  const [sortKey, setSortKey] = useState("price_b"); // price_a, price_b, delta_abs, delta_pct
  const [sortDir, setSortDir] = useState("desc");

  // Auto-load default snapshots from repo (v0.1/v0.2)
  useEffect(() => {
    const loadDefaults = async () => {
      const base = baseUrl();
      try {
        if (!pricesA) {
          const rows = await loadCSVFromUrl(`${base}data/snapshots/prices_v0_1.csv`);
          setPricesA({ name: "prices_v0_1.csv", rows });
        }
        if (!pricesB) {
          const rows = await loadCSVFromUrl(`${base}data/snapshots/prices_v0_2.csv`);
          setPricesB({ name: "prices_v0_2.csv", rows });
        }
        if (!recipes) {
          const obj = await loadJSONFromUrl(`${base}data/extracted/recipes.json`);
          setRecipes({ name: "recipes.json", obj });
        }
        if (!recipeKeyMap) {
          const obj = await loadJSONFromUrl(`${base}data/extracted/recipe_key_map.json`);
          setRecipeKeyMap({ name: "recipe_key_map.json", obj });
        }
        if (!overrides) {
          // prefer localStorage if present
          const local = localStorage.getItem("nyrell_overrides");
          if (local) {
            setOverrides({ name: "overrides.local.json", obj: JSON.parse(local) });
          } else {
            const obj = await loadJSONFromUrl(`${base}data/overrides/overrides.json`);
            setOverrides({ name: "overrides.json", obj });
          }
        }
      } catch {
        // ignore if files not present
      }
    };
    loadDefaults();
  }, []);

  function handleCSV(setter) {
    return async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const text = await file.text();
      const rows = parseCSV(text);
      setter({ name: file.name, rows });
      setSelectedId(null);
    };
  }

  function handleJSON(setter) {
    return async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const obj = await loadJSONFile(file);
      setter({ name: file.name, obj });
    };
  }

  const merged = useMemo(() => {
    const a = pricesA?.rows ?? [];
    const b = pricesB?.rows ?? [];
    const map = new Map();

    for (const r of a) {
      map.set(r.canonical_id, {
        canonical_id: r.canonical_id,
        canonical_kind: r.canonical_kind,
        profile: r.profile,
        zone: r.zone,
        rarity_tag: r.rarity_tag,
        calc_a: r.calc,
        recipe_key_a: r.recipe_key,
        missing_inputs_a: r.missing_inputs,
        icon_path_a: r.icon_path,
        bundle_qty_a: r.bundle_qty,
        minutes_a: r.minutes_per_unit,
        price_a: num(r.price_nyra),
      });
    }
    for (const r of b) {
      const prev = map.get(r.canonical_id) ?? { canonical_id: r.canonical_id };
      map.set(r.canonical_id, {
        ...prev,
        canonical_kind: r.canonical_kind ?? prev.canonical_kind,
        profile: r.profile ?? prev.profile,
        zone: r.zone ?? prev.zone,
        rarity_tag: r.rarity_tag ?? prev.rarity_tag,
        calc_b: r.calc,
        recipe_key_b: r.recipe_key,
        missing_inputs_b: r.missing_inputs,
        icon_path_b: r.icon_path ?? prev.icon_path_b,
        bundle_qty_b: r.bundle_qty,
        minutes_b: r.minutes_per_unit,
        price_b: num(r.price_nyra),
      });
    }

    return Array.from(map.values()).map((r) => {
      const aP = r.price_a;
      const bP = r.price_b;
      const delta = aP != null && bP != null ? bP - aP : null;
      const pct = aP != null && bP != null && aP !== 0 ? (delta / aP) * 100 : null;
      return { ...r, delta, pct };
    });
  }, [pricesA, pricesB]);

  const priceLookup = useMemo(() => {
    // prefer B, else A
    const m = new Map();
    for (const r of merged) {
      const p = r.price_b ?? r.price_a;
      const b = num(r.bundle_qty_b ?? r.bundle_qty_a) ?? 1;
      const icon = r.icon_path_b ?? r.icon_path_a ?? "";
      if (p != null) m.set(r.canonical_id, { bundle: b, price: p, unit: p / b, icon_path: icon });
    }
    return m;
  }, [merged]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return merged
      .filter((r) => {
        if (q && !(r.canonical_id ?? "").toLowerCase().includes(q)) return false;
        if (filterZone !== "all" && String(r.zone) !== filterZone) return false;
        if (filterRarity !== "all" && String(r.rarity_tag) !== filterRarity) return false;
        if (filterKind !== "all" && String(r.canonical_kind) !== filterKind) return false;

        const calc = r.calc_b ?? r.calc_a ?? "";
        if (filterCalc !== "all" && calc !== filterCalc) return false;

        if (onlyChanged) {
          if (r.delta == null) return false;
          if (Math.abs(r.delta) < 0.0001) return false;
        }
        return true;
      })
      .sort((x, y) => {
        const dir = sortDir === "asc" ? 1 : -1;
        const get = (r) => {
          if (sortKey === "price_a") return r.price_a ?? -Infinity;
          if (sortKey === "price_b") return r.price_b ?? -Infinity;
          if (sortKey === "delta_abs") return r.delta ?? -Infinity;
          if (sortKey === "delta_pct") return r.pct ?? -Infinity;
          return r.price_b ?? -Infinity;
        };
        const ax = get(x);
        const ay = get(y);
        if (ax < ay) return -1 * dir;
        if (ax > ay) return 1 * dir;
        return (x.canonical_id ?? "").localeCompare(y.canonical_id ?? "");
      });
  }, [merged, search, filterZone, filterRarity, filterKind, filterCalc, onlyChanged, sortKey, sortDir]);

  const selected = useMemo(
    () => filtered.find((r) => r.canonical_id === selectedId) ?? merged.find((r) => r.canonical_id === selectedId),
    [filtered, merged, selectedId]
  );
  const appBase = import.meta.env.BASE_URL || "/";
  const iconPath = selected?.icon_path_b || selected?.icon_path_a || "";
  const iconUrl = iconPath
    ? iconBaseUrl
      ? `${iconBaseUrl.replace(/\/$/, "")}/${iconPath.replace(/^\/+/, "")}`
      : `${appBase}${iconPath.replace(/^\/+/, "")}`
    : "";

  const iconForPath = (p) => {
    if (!p) return "";
    return iconBaseUrl
      ? `${iconBaseUrl.replace(/\/$/, "")}/${p.replace(/^\/+/, "")}`
      : `${appBase}${p.replace(/^\/+/, "")}`;
  };

  const iconFallbackForPath = (p) => {
    if (!p) return "";
    return `${appBase}${p.replace(/^\/+/, "")}`;
  };

  useEffect(() => {
    if (!selected) return;
    const cur = overridesMap[selected.canonical_id] ?? {};
    setOverrideDraft({
      price_nyra: cur.price_nyra ?? "",
      floor_nyra: cur.floor_nyra ?? "",
      ceil_nyra: cur.ceil_nyra ?? "",
      disable_bom: !!cur.disable_bom,
      note: cur.note ?? "",
    });
  }, [selectedId, overrides]);

  const zones = useMemo(() => {
    const s = new Set();
    for (const r of merged) if (r.zone != null) s.add(String(r.zone));
    return ["all", ...Array.from(s).sort()];
  }, [merged]);

  const rarities = useMemo(() => {
    const s = new Set();
    for (const r of merged) if (r.rarity_tag) s.add(String(r.rarity_tag));
    return ["all", ...Array.from(s).sort()];
  }, [merged]);

  const kinds = useMemo(() => {
    const s = new Set();
    for (const r of merged) if (r.canonical_kind) s.add(String(r.canonical_kind));
    return ["all", ...Array.from(s).sort()];
  }, [merged]);

  const calcs = useMemo(() => {
    const s = new Set();
    for (const r of merged) {
      const c = r.calc_b ?? r.calc_a;
      if (c) s.add(String(c));
    }
    return ["all", ...Array.from(s).sort()];
  }, [merged]);

  const stats = useMemo(() => {
    const shown = filtered;
    const count = shown.length;
    const changed = shown.filter((r) => r.delta != null && Math.abs(r.delta) > 0.0001).length;
    const pctVals = shown.map((r) => r.pct).filter((v) => v != null && Number.isFinite(v));
    const avgPct = pctVals.reduce((a, b) => a + b, 0) / Math.max(1, pctVals.length);
    return { count, changed, avgPct: Number.isFinite(avgPct) ? avgPct : 0 };
  }, [filtered]);

  function upsertOverride() {
    if (!selected) return;
    const id = selected.canonical_id;
    const payload = normalizeOverridesPayload(overrides?.obj);
    const obj = { ...payload.overrides };

    const cleanNum = (v) => {
      if (v === "" || v == null) return undefined;
      const n = Number(v);
      return Number.isFinite(n) ? n : undefined;
    };

    const entry = {
      price_nyra: cleanNum(overrideDraft.price_nyra),
      floor_nyra: cleanNum(overrideDraft.floor_nyra),
      ceil_nyra: cleanNum(overrideDraft.ceil_nyra),
      disable_bom: overrideDraft.disable_bom ? true : undefined,
      note: overrideDraft.note?.trim() ? overrideDraft.note.trim() : undefined,
    };

    Object.keys(entry).forEach((k) => entry[k] === undefined && delete entry[k]);

    if (Object.keys(entry).length === 0) {
      delete obj[id];
    } else {
      obj[id] = entry;
    }

    setOverrides({ name: "overrides.json", obj: { meta: payload.meta, overrides: obj } });
  }

  function downloadOverrides() {
    const payload = normalizeOverridesPayload(overrides?.obj);
    const finalPayload = {
      meta: {
        author: payload.meta.author ?? "local",
        timestamp: new Date().toISOString(),
      },
      overrides: payload.overrides,
    };
    const text = JSON.stringify(finalPayload, null, 2);
    const blob = new Blob([text], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "overrides.json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function saveOverridesLocal() {
    const payload = normalizeOverridesPayload(overrides?.obj);
    const finalPayload = {
      meta: {
        author: payload.meta.author ?? "local",
        timestamp: new Date().toISOString(),
      },
      overrides: payload.overrides,
    };
    localStorage.setItem("nyrell_overrides", JSON.stringify(finalPayload));
    setOverrides({ name: "overrides.local.json", obj: finalPayload });
  }

  function openOverrideIssue() {
    const obj = overridesMap;
    const selectedKey = selected?.canonical_id;
    const selectedExample =
      selectedKey && !obj[selectedKey]
        ? { [selectedKey]: { price_nyra: 200.0, note: "Beispiel override" } }
        : null;
    const payload = {
      meta: {
        author: "TODO:dein_github_name",
        timestamp: new Date().toISOString(),
      },
      overrides: Object.keys(obj).length
        ? obj
        : selectedExample ??
          {
            "BAR:prisma": { price_nyra: 200.0, note: "Beispiel override" },
          },
    };
    const json = JSON.stringify(payload, null, 2);
    const title = encodeURIComponent("Override Update");
    const body = encodeURIComponent(
      "Bitte GitHub-Username eintragen und Overrides prüfen.\n\n```json\n" +
        json +
        "\n```"
    );
    const url =
      "https://github.com/Noxitanius/Itempreise/issues/new?labels=overrides&title=" +
      title +
      "&body=" +
      body;
    window.open(url, "_blank");
  }

  function exportFiltered() {
    const rows = filtered.map((r) => ({
      canonical_id: r.canonical_id,
      canonical_kind: r.canonical_kind ?? "",
      zone: r.zone ?? "",
      rarity_tag: r.rarity_tag ?? "",
      profile: r.profile ?? "",
      calc_a: r.calc_a ?? "",
      price_a: r.price_a ?? "",
      calc_b: r.calc_b ?? "",
      price_b: r.price_b ?? "",
      delta: r.delta ?? "",
      pct: r.pct ?? "",
      recipe_key_b: r.recipe_key_b ?? "",
      missing_inputs_b: r.missing_inputs_b ?? "",
    }));

    const headers = Object.keys(rows[0] ?? { canonical_id: "" });
    const csv = toCSV(rows, headers);
    const ts = new Date().toISOString().slice(0, 19).replaceAll(":", "-");
    downloadText(`export_filtered_${ts}.csv`, csv);
  }

  function exportAnomalies() {
    if (!anomalies.length) return;
    const rows = anomalies.map((a) => ({
      severity: a.severity,
      type: a.type,
      canonical_id: a.canonical_id,
      message: a.message,
    }));
    const headers = ["severity", "type", "canonical_id", "message"];
    const csv = toCSV(rows, headers);
    const ts = new Date().toISOString().slice(0, 19).replaceAll(":", "-");
    downloadText(`export_anomalies_${ts}.csv`, csv);
  }

  const bom = useMemo(() => {
    if (!selected || !recipes?.obj || !recipeKeyMap?.obj) return null;

    // pick recipe key: prefer snapshot B recipe_key, else map
    const recipeKey =
      selected.recipe_key_b ||
      selected.recipe_key_a ||
      (recipeKeyMap.obj[selected.canonical_id]?.[0] ?? "");

    if (!recipeKey) return { recipeKey: "", inputs: [], note: "No recipe_key available." };

    const recipe = recipes.obj[recipeKey];
    if (!recipe) return { recipeKey, inputs: [], note: "Recipe key not found in recipes.json." };

    const inputs = (recipe.inputs ?? []).map((inp) => {
      const canon = toCanonicalFromRecipeInput(inp);
      const qty = Number(inp.qty ?? 0) || 0;
      const pricing = canon ? priceLookup.get(canon) : null;
      const unit = pricing?.unit ?? null;
      const cost = unit != null ? unit * qty : null;
      return { ...inp, canonical: canon, qty, unitPrice: unit, cost };
    });

    const total = inputs.reduce((acc, it) => acc + (it.cost ?? 0), 0);
    const missing = inputs.filter((x) => x.canonical && !priceLookup.has(x.canonical)).map((x) => x.canonical);

    return {
      recipeKey,
      timeSeconds: recipe.time_seconds ?? 0,
      knowledgeRequired: !!recipe.knowledge_required,
      inputs,
      totalUnitCost: total,
      missing,
      note: "",
    };
  }, [selected, recipes, recipeKeyMap, priceLookup]);

  const anomalies = useMemo(() => {
    // needs prices and ideally recipes to be meaningful
    if (!merged.length) return [];

    const out = [];

    // helper: get price (prefer B), plus calc
    const getPrice = (r) => r.price_b ?? r.price_a;
    const getCalc = (r) => r.calc_b ?? r.calc_a ?? "";

    // anchor references (helps detect “farm too strong”)
    const oreT1Bar =
      merged.find((x) => x.canonical_id === "BAR:copper") ||
      merged.find((x) => x.canonical_id === "BAR:iron");
    const oreT1Price = oreT1Bar ? getPrice(oreT1Bar) : null; // per bundle 100

    for (const r of merged) {
      const id = r.canonical_id;
      const price = getPrice(r);
      const calc = getCalc(r);

      if (price == null) continue;

      // 1) Floor dominates (heuristic)
      if ((calc || "").toLowerCase().includes("floor")) {
        out.push({
          severity: "info",
          type: "floor",
          canonical_id: id,
          message: "Price is floor-driven (calc=floor).",
        });
      }

      // 2) BOM exists but missing inputs (from snapshot)
      const missing = (r.missing_inputs_b || r.missing_inputs_a || "").trim();
      if (missing) {
        out.push({
          severity: "warn",
          type: "bom_missing",
          canonical_id: id,
          message: `BOM missing inputs: ${missing}`,
        });
      }

      // 3) Crop/Essence risk vs BAR:copper anchor
      if (oreT1Price != null) {
        if (id.startsWith("CROP:") && price > oreT1Price * 1.2) {
          out.push({
            severity: "warn",
            type: "farm_expensive",
            canonical_id: id,
            message:
              "Crop bundle pricier than BAR:t1 anchor (risk: low demand, dead market).",
          });
        }
        if (id.startsWith("CROP:") && price < oreT1Price * 0.05) {
          out.push({
            severity: "warn",
            type: "farm_cheap",
            canonical_id: id,
            message:
              "Crop bundle extremely cheap vs BAR:t1 (risk: money-print if sold-for-cash exists elsewhere).",
          });
        }
        if (id.startsWith("ESSENCE:") && price < oreT1Price * 0.03) {
          out.push({
            severity: "warn",
            type: "essence_cheap",
            canonical_id: id,
            message:
              "Essence very cheap vs BAR:t1 (risk: floods market if used broadly).",
          });
        }
      }

      // 4) Unchanged between A and B (informational)
      if (r.price_a != null && r.price_b != null && Math.abs(r.price_b - r.price_a) < 1e-6) {
        out.push({
          severity: "info",
          type: "unchanged",
          canonical_id: id,
          message: "No delta A→B (same calc or floors dominating).",
        });
      }
    }

    // 5) Selected-item BOM vs final-price mismatch (only for selected & bom)
    if (selected && bom && bom.inputs?.length) {
      const p = selected.price_b ?? selected.price_a;
      const bundle = Number(selected.bundle_qty_b ?? selected.bundle_qty_a) || 1;
      const bomUnit = Number(bom.totalUnitCost ?? 0);
      const bomBundle = bomUnit * bundle;
      if (p != null && bomBundle > 0) {
        const ratio = p / bomBundle;
        if (ratio > 1.8) {
          out.push({
            severity: "warn",
            type: "price_over_bom",
            canonical_id: selected.canonical_id,
            message:
              "Selected: Price is > 1.8× BOM estimate (check floors/zone/rarity).",
          });
        }
        if (ratio < 0.6) {
          out.push({
            severity: "warn",
            type: "price_under_bom",
            canonical_id: selected.canonical_id,
            message:
              "Selected: Price is < 0.6× BOM estimate (likely mispricing / floor too low).",
          });
        }
      }
    }

    const severityRank = { crit: 0, warn: 1, info: 2 };
    out.sort(
      (a, b) =>
        (severityRank[a.severity] ?? 9) - (severityRank[b.severity] ?? 9) ||
        a.canonical_id.localeCompare(b.canonical_id)
    );
    return out;
  }, [merged, selected, bom]);

  const shell = {
    fontFamily: "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial",
    background: "#071416",
    color: "#e8f6f6",
    minHeight: "100vh",
    padding: 20,
    overflowX: "hidden",
  };

  const card = {
    background: "rgba(10, 24, 28, 0.9)",
    border: "1px solid rgba(76, 180, 170, 0.18)",
    borderRadius: 16,
    padding: 16,
  };

  const inputStyle = {
    background: "#0d1f24",
    border: "1px solid rgba(76, 180, 170, 0.22)",
    borderRadius: 12,
    padding: "10px 12px",
    color: "#e8f6f6",
    width: "100%",
    boxSizing: "border-box",
    outline: "none",
  };

  const fileButtonStyle = {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "100%",
    boxSizing: "border-box",
    padding: "8px 12px",
    borderRadius: 10,
    border: "1px solid rgba(76, 180, 170, 0.24)",
    background: "rgba(13, 31, 36, 0.9)",
    color: "#e8f6f6",
    cursor: "pointer",
    fontWeight: 600,
    fontSize: 12,
  };

  const fileLabelStyle = {
    display: "block",
    width: "100%",
  };

  const selectStyle = {
    ...inputStyle,
    padding: "10px 10px",
    color: "#0b1214",
    background: "#dff2f1",
  };

  return (
    <div style={{ ...shell, overflowX: "hidden" }}>
      <div style={{ width: "100%", maxWidth: "100vw", margin: "0 auto", padding: 0, boxSizing: "border-box" }}>
        <div style={{ width: "100%", maxWidth: "100vw", margin: "0 auto", padding: "0 16px", boxSizing: "border-box" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <img src={logo} alt="Nyrell" style={{ width: 56, height: 56 }} />
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: 0.2 }}>Nyrell Economy UI</div>
              <div style={{ opacity: 0.8, marginTop: 4, fontSize: 13 }}>
                Load snapshots, filter, compare deltas, inspect BOM (recipes.json + key map).
              </div>
            </div>
          </div>
          <div style={{ opacity: 0.75, fontSize: 13, textAlign: "right" }}>
            {badge(`Shown: ${stats.count}`)}
            {badge(`Changed: ${stats.changed}`)}
            {badge(`Avg Δ%: ${stats.avgPct.toFixed(1)}%`)}
          </div>
        </div>

        <div className="main-grid">
          <div style={card}>
            <Section title="Load files">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: 12,
                  alignItems: "start",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>Snapshot A (v0.1)</div>
                  <label htmlFor="file-snap-a" style={fileLabelStyle}>
                    <span style={fileButtonStyle}>Datei auswählen</span>
                  </label>
                  <input id="file-snap-a" type="file" accept=".csv" onChange={handleCSV(setPricesA)} style={{ display: "none" }} />
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>{pricesA ? pricesA.name : "Keine ausgewählt"}</div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>Snapshot B (v0.2)</div>
                  <label htmlFor="file-snap-b" style={fileLabelStyle}>
                    <span style={fileButtonStyle}>Datei auswählen</span>
                  </label>
                  <input id="file-snap-b" type="file" accept=".csv" onChange={handleCSV(setPricesB)} style={{ display: "none" }} />
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>{pricesB ? pricesB.name : "Keine ausgewählt"}</div>
                </div>
              </div>

              <div style={{ height: 10 }} />

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: 12,
                  alignItems: "start",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>recipes.json</div>
                  <label htmlFor="file-recipes" style={fileLabelStyle}>
                    <span style={fileButtonStyle}>Datei auswählen</span>
                  </label>
                  <input id="file-recipes" type="file" accept=".json" onChange={handleJSON(setRecipes)} style={{ display: "none" }} />
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>{recipes ? recipes.name : "Keine ausgewählt"}</div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>recipe_key_map.json</div>
                  <label htmlFor="file-keymap" style={fileLabelStyle}>
                    <span style={fileButtonStyle}>Datei auswählen</span>
                  </label>
                  <input id="file-keymap" type="file" accept=".json" onChange={handleJSON(setRecipeKeyMap)} style={{ display: "none" }} />
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>{recipeKeyMap ? recipeKeyMap.name : "Keine ausgewählt"}</div>
                </div>
              </div>

              <div style={{ height: 10 }} />

              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>overrides.json</div>
                  <label htmlFor="file-overrides" style={fileLabelStyle}>
                    <span style={fileButtonStyle}>Datei auswählen</span>
                  </label>
                  <input id="file-overrides" type="file" accept=".json" onChange={handleJSON(setOverrides)} style={{ display: "none" }} />
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>{overrides ? overrides.name : "Keine ausgewählt"}</div>
                </div>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>Defaults</div>
                  <button
                    onClick={async () => {
                      const base = baseUrl();
                      const rowsA = await loadCSVFromUrl(`${base}data/snapshots/prices_v0_1.csv`);
                      const rowsB = await loadCSVFromUrl(`${base}data/snapshots/prices_v0_2.csv`);
                      setPricesA({ name: "prices_v0_1.csv", rows: rowsA });
                      setPricesB({ name: "prices_v0_2.csv", rows: rowsB });
                      const r = await loadJSONFromUrl(`${base}data/extracted/recipes.json`);
                      const k = await loadJSONFromUrl(`${base}data/extracted/recipe_key_map.json`);
                      setRecipes({ name: "recipes.json", obj: r });
                      setRecipeKeyMap({ name: "recipe_key_map.json", obj: k });
                      const ov = await loadJSONFromUrl(`${base}data/overrides/overrides.json`);
                      setOverrides({ name: "overrides.json", obj: ov });
                    }}
                    style={fileButtonStyle}
                  >
                    Defaults laden
                  </button>
                  <div style={{ marginTop: 6, opacity: 0.8, fontSize: 12 }}>A=v0.1, B=v0.2</div>
                </div>
              </div>
            </Section>

            <Section title="Filters">
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                  gap: 10,
                  alignItems: "center",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <input
                    style={{ ...inputStyle, minWidth: 0 }}
                    placeholder="Search canonical_id (e.g. BAR:mithril, ORE_ITEM:Ore_Prisma)"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                <div style={{ minWidth: 0 }}>
                  <select style={{ ...selectStyle, minWidth: 0 }} value={filterZone} onChange={(e) => setFilterZone(e.target.value)}>
                    {zones.map((z) => (
                      <option key={z} value={z}>
                        {z === "all" ? "Zone: all" : `Zone ${z}`}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ minWidth: 0 }}>
                  <select
                    style={{ ...selectStyle, minWidth: 0 }}
                    value={filterRarity}
                    onChange={(e) => setFilterRarity(e.target.value)}
                  >
                    {rarities.map((r) => (
                      <option key={r} value={r}>
                        {r === "all" ? "Rarity: all" : r}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                  gap: 10,
                  marginTop: 10,
                  alignItems: "center",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <select style={{ ...selectStyle, minWidth: 0 }} value={filterKind} onChange={(e) => setFilterKind(e.target.value)}>
                    {kinds.map((k) => (
                      <option key={k} value={k}>
                        {k === "all" ? "Kind: all" : k}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ minWidth: 0 }}>
                  <select style={{ ...selectStyle, minWidth: 0 }} value={filterCalc} onChange={(e) => setFilterCalc(e.target.value)}>
                    {calcs.map((c) => (
                      <option key={c} value={c}>
                        {c === "all" ? "Calc: all" : c}
                      </option>
                    ))}
                  </select>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <input type="checkbox" checked={onlyChanged} onChange={(e) => setOnlyChanged(e.target.checked)} />
                  <div style={{ opacity: 0.85, fontSize: 13, whiteSpace: "nowrap" }}>Only changed</div>
                </div>
              </div>
            </Section>

            <Section title="Sort">
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <select style={selectStyle} value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                  <option value="price_b">Price (B)</option>
                  <option value="price_a">Price (A)</option>
                  <option value="delta_abs">Δ abs</option>
                  <option value="delta_pct">Δ %</option>
                </select>
                <select style={selectStyle} value={sortDir} onChange={(e) => setSortDir(e.target.value)}>
                  <option value="desc">Desc</option>
                  <option value="asc">Asc</option>
                </select>
              </div>
            </Section>
          </div>

          <div style={card}>
            <Section title="Selected item">
              {!selected ? (
                <div style={{ opacity: 0.75, fontSize: 13 }}>
                  Click an entry in the table. Tip: search for <b>BAR:prisma</b> or <b>ORE_ITEM:Ore_Prisma</b>.
                </div>
              ) : (
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                    {iconUrl ? (
                      <img
                        src={iconUrl}
                        alt=""
                        style={{ width: 28, height: 28, borderRadius: 6 }}
                        onError={(e) => {
                          const fb = iconFallbackForPath(iconPath);
                          if (fb && e.currentTarget.src !== fb) e.currentTarget.src = fb;
                        }}
                      />
                    ) : null}
                    <div style={{ fontSize: 16, fontWeight: 800 }}>{selected.canonical_id}</div>
                  </div>
                  <div style={{ opacity: 0.85, fontSize: 13, lineHeight: 1.65 }}>
                    {badge(selected.canonical_kind ?? "—")}
                    {badge(`zone ${selected.zone ?? "—"}`)}
                    {badge(selected.rarity_tag ?? "—")}
                    {badge(selected.profile ?? "—")}
                  </div>

                  <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                    <div style={{ padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                      <div style={{ fontSize: 12, opacity: 0.75 }}>Snapshot A</div>
                      <div style={{ marginTop: 6, fontWeight: 800 }}>{selected.price_a != null ? `${selected.price_a.toFixed(2)} Nyra` : "—"}</div>
                      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.75 }}>
                        calc: {selected.calc_a ?? "—"} <br />
                        bundle: {selected.bundle_qty_a ?? "—"} <br />
                        mpu: {selected.minutes_a ?? "—"}
                      </div>
                    </div>

                    <div style={{ padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}>
                      <div style={{ fontSize: 12, opacity: 0.75 }}>Snapshot B</div>
                      <div style={{ marginTop: 6, fontWeight: 800 }}>{selected.price_b != null ? `${selected.price_b.toFixed(2)} Nyra` : "—"}</div>
                      <div style={{ marginTop: 6, fontSize: 12, opacity: 0.75 }}>
                        calc: {selected.calc_b ?? "—"} <br />
                        bundle: {selected.bundle_qty_b ?? "—"} <br />
                        mpu: {selected.minutes_b ?? "—"}
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: 12, padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 6 }}>Delta</div>
                    <div style={{ fontWeight: 800 }}>
                      {selected.delta == null ? "—" : `${selected.delta >= 0 ? "+" : ""}${selected.delta.toFixed(2)} Nyra`}
                      <span style={{ opacity: 0.7, marginLeft: 10, fontWeight: 600 }}>
                        {selected.pct == null ? "" : `(${selected.pct >= 0 ? "+" : ""}${selected.pct.toFixed(1)}%)`}
                      </span>
                    </div>
                  </div>

                  <div style={{ marginTop: 14, padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 8 }}>Recipe / BOM</div>
                    {!bom ? (
                      <div style={{ opacity: 0.75, fontSize: 13 }}>Load recipes.json + recipe_key_map.json to view BOM.</div>
                    ) : (
                      <div style={{ fontSize: 13, lineHeight: 1.55 }}>
                        <div>
                          {badge(`recipe: ${bom.recipeKey || "—"}`)}
                          {badge(`knowledge: ${bom.knowledgeRequired ? "yes" : "no"}`)}
                          {badge(`time: ${bom.timeSeconds ?? 0}s`)}
                        </div>

                        {bom.note ? <div style={{ opacity: 0.75, marginTop: 8 }}>{bom.note}</div> : null}

                        <div style={{ marginTop: 10 }}>
                          <div style={{ opacity: 0.85, fontWeight: 700, marginBottom: 6 }}>Inputs</div>
                          {bom.inputs.length === 0 ? (
                            <div style={{ opacity: 0.75 }}>No inputs.</div>
                          ) : (
                            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 6 }}>
                              {bom.inputs.map((i, idx) => (
                                <div
                                  key={idx}
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    gap: 10,
                                    padding: "8px 10px",
                                    borderRadius: 12,
                                    background: "rgba(255,255,255,0.03)",
                                    border: "1px solid rgba(255,255,255,0.08)",
                                  }}
                                >
                                  <div style={{ minWidth: 0 }}>
                                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                      {i.canonical && priceLookup.get(i.canonical)?.icon_path ? (
                                        <img
                                          src={iconForPath(priceLookup.get(i.canonical)?.icon_path)}
                                          alt=""
                                          style={{ width: 18, height: 18, borderRadius: 4 }}
                                          onError={(e) => {
                                            const fb = iconFallbackForPath(
                                              priceLookup.get(i.canonical)?.icon_path
                                            );
                                            if (fb && e.currentTarget.src !== fb)
                                              e.currentTarget.src = fb;
                                          }}
                                        />
                                      ) : null}
                                      <div style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 }}>
                                        {i.id} {i.canonical ? `→ ${i.canonical}` : ""}
                                      </div>
                                    </div>
                                    <div style={{ opacity: 0.75, fontSize: 12 }}>
                                      qty: {i.qty}
                                      {i.unitPrice != null ? ` | unit: ${i.unitPrice.toFixed(4)} Nyra` : " | unit: —"}
                                    </div>
                                  </div>
                                  <div style={{ fontWeight: 800 }}>
                                    {i.cost != null ? `${i.cost.toFixed(4)} Nyra` : "—"}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.10)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <div style={{ opacity: 0.8 }}>Total (unit inputs cost)</div>
                            <div style={{ fontWeight: 900 }}>{(bom.totalUnitCost ?? 0).toFixed(4)} Nyra</div>
                          </div>
                          {bom.missing?.length ? (
                            <div style={{ marginTop: 8, opacity: 0.75 }}>
                              Missing priced inputs: {bom.missing.join(", ")}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </div>

                  <div style={{ marginTop: 12, fontSize: 12, opacity: 0.75 }}>
                    recipe_key(B): {selected.recipe_key_b || "—"} <br />
                    missing_inputs(B): {selected.missing_inputs_b || "—"}
                    <br />
                    icon_path: {selected.icon_path_b || selected.icon_path_a || "—"}
                  </div>

                  <div style={{ marginTop: 14, padding: 12, borderRadius: 14, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.08)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
                      <div style={{ fontSize: 12, opacity: 0.75, fontWeight: 700 }}>Overrides</div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                        <button
                          onClick={openOverrideIssue}
                          style={{
                            padding: "8px 10px",
                            borderRadius: 12,
                            border: "1px solid rgba(255,255,255,0.14)",
                            background: "rgba(255,255,255,0.06)",
                            color: "rgba(255,255,255,0.92)",
                            cursor: "pointer",
                            fontWeight: 700,
                            fontSize: 12,
                          }}
                          title="Erstellt ein Issue mit Overrides für automatischen PR"
                        >
                          Preisänderung beantragen
                        </button>
                        <button
                          onClick={saveOverridesLocal}
                          style={{
                            padding: "8px 10px",
                            borderRadius: 12,
                            border: "1px solid rgba(255,255,255,0.14)",
                            background: "rgba(255,255,255,0.06)",
                            color: "rgba(255,255,255,0.92)",
                            cursor: "pointer",
                            fontWeight: 700,
                            fontSize: 12,
                          }}
                          title="Speichert Overrides im Browser (localStorage)"
                        >
                          Save local
                        </button>
                      </div>
                    </div>

                    <div
                      style={{
                        marginTop: 10,
                        display: "grid",
                        gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                        gap: 10,
                      }}
                    >
                      <div>
                        <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 6 }}>price_nyra (bundle)</div>
                        <input
                          style={{ ...inputStyle, minWidth: 0 }}
                          value={overrideDraft.price_nyra}
                          onChange={(e) => setOverrideDraft((d) => ({ ...d, price_nyra: e.target.value }))}
                          placeholder="e.g. 180"
                        />
                      </div>
                      <div>
                        <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 6 }}>floor_nyra (bundle)</div>
                        <input
                          style={{ ...inputStyle, minWidth: 0 }}
                          value={overrideDraft.floor_nyra}
                          onChange={(e) => setOverrideDraft((d) => ({ ...d, floor_nyra: e.target.value }))}
                          placeholder="e.g. 120"
                        />
                      </div>
                      <div>
                        <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 6 }}>ceil_nyra (bundle)</div>
                        <input
                          style={{ ...inputStyle, minWidth: 0 }}
                          value={overrideDraft.ceil_nyra}
                          onChange={(e) => setOverrideDraft((d) => ({ ...d, ceil_nyra: e.target.value }))}
                          placeholder="e.g. 260"
                        />
                      </div>
                    </div>

                    <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 10 }}>
                      <input
                        type="checkbox"
                        checked={overrideDraft.disable_bom}
                        onChange={(e) => setOverrideDraft((d) => ({ ...d, disable_bom: e.target.checked }))}
                      />
                      <div style={{ opacity: 0.85, fontSize: 13 }}>disable_bom</div>
                    </div>

                    <div style={{ marginTop: 10 }}>
                      <div style={{ fontSize: 12, opacity: 0.75, marginBottom: 6 }}>note</div>
                      <input
                        style={inputStyle}
                        value={overrideDraft.note}
                        onChange={(e) => setOverrideDraft((d) => ({ ...d, note: e.target.value }))}
                        placeholder="why this override exists"
                      />
                    </div>

                    <div style={{ marginTop: 10, opacity: 0.7, fontSize: 12 }}>
                      Loaded overrides: {Object.keys(overridesMap ?? {}).length}
                    </div>
                  </div>
                </div>
              )}
            </Section>
          </div>

          <div style={card}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
              <div style={{ fontWeight: 800 }}>Price table</div>

              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <button
                  onClick={exportFiltered}
                  disabled={filtered.length === 0}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.14)",
                    background: "rgba(255,255,255,0.06)",
                    color: "rgba(255,255,255,0.92)",
                    cursor: filtered.length === 0 ? "not-allowed" : "pointer",
                    opacity: filtered.length === 0 ? 0.5 : 1,
                    fontWeight: 700,
                    fontSize: 12,
                  }}
                  title="Exports current filtered rows as CSV"
                >
                  Export filtered (CSV)
                </button>

                <button
                  onClick={exportAnomalies}
                  disabled={anomalies.length === 0}
                  style={{
                    padding: "8px 10px",
                    borderRadius: 12,
                    border: "1px solid rgba(255,255,255,0.14)",
                    background: "rgba(255,255,255,0.06)",
                    color: "rgba(255,255,255,0.92)",
                    cursor: anomalies.length === 0 ? "not-allowed" : "pointer",
                    opacity: anomalies.length === 0 ? 0.5 : 1,
                    fontWeight: 700,
                    fontSize: 12,
                  }}
                  title="Exports anomalies list as CSV"
                >
                  Export anomalies (CSV)
                </button>

                <div style={{ opacity: 0.75, fontSize: 12 }}>
                  Tip: “Only changed” isolates telemetry impact.
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: 12,
                overflow: "auto",
                maxHeight: 700,
                borderRadius: 14,
                border: "1px solid rgba(255,255,255,0.08)",
              }}
            >
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead style={{ position: "sticky", top: 0, background: "#0b0f14" }}>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                    {["canonical_id", "kind", "zone", "rarity", "calc(B)", "price(A)", "price(B)", "Δ", "Δ%"].map((h) => (
                      <th key={h} style={{ padding: "10px 12px", opacity: 0.85, fontWeight: 700, whiteSpace: "nowrap" }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r) => (
                    <tr
                      key={r.canonical_id}
                      onClick={() => setSelectedId(r.canonical_id)}
                      style={{
                        cursor: "pointer",
                        background: r.canonical_id === selectedId ? "rgba(255,255,255,0.06)" : "transparent",
                        borderBottom: "1px solid rgba(255,255,255,0.06)",
                      }}
                    >
                    <td style={{ padding: "10px 12px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        {(r.icon_path_b || r.icon_path_a) ? (
                          <img
                            src={iconForPath(r.icon_path_b || r.icon_path_a)}
                            alt=""
                            style={{ width: 18, height: 18, borderRadius: 4 }}
                            onError={(e) => {
                              const fb = iconFallbackForPath(r.icon_path_b || r.icon_path_a);
                              if (fb && e.currentTarget.src !== fb) e.currentTarget.src = fb;
                            }}
                          />
                        ) : null}
                        <span style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace", fontSize: 12 }}>
                          {r.canonical_id}
                        </span>
                      </div>
                    </td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{r.canonical_kind ?? "—"}</td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{r.zone ?? "—"}</td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{r.rarity_tag ?? "—"}</td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{r.calc_b ?? r.calc_a ?? "—"}</td>
                      <td style={{ padding: "10px 12px" }}>{r.price_a == null ? "—" : r.price_a.toFixed(2)}</td>
                      <td style={{ padding: "10px 12px" }}>{r.price_b == null ? "—" : r.price_b.toFixed(2)}</td>
                      <td style={{ padding: "10px 12px" }}>
                        {r.delta == null ? "—" : `${r.delta >= 0 ? "+" : ""}${r.delta.toFixed(2)}`}
                      </td>
                      <td style={{ padding: "10px 12px" }}>
                        {r.pct == null ? "—" : `${r.pct >= 0 ? "+" : ""}${r.pct.toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ padding: 16, opacity: 0.75 }}>
                        No rows. Load snapshots or adjust filters.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: 10, opacity: 0.7, fontSize: 12 }}>
              Loaded: A={pricesA ? pricesA.rows.length : 0} rows, B={pricesB ? pricesB.rows.length : 0} rows
            </div>
          </div>
        </div>

        <div style={{ ...card, marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
            <div style={{ fontWeight: 800 }}>Anomaly Scanner</div>
            <div style={{ opacity: 0.75, fontSize: 12 }}>
              Click an entry to jump to it (uses canonical_id).
            </div>
          </div>

          <div
            style={{
              marginTop: 12,
              overflow: "auto",
              maxHeight: 320,
              borderRadius: 14,
              border: "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead style={{ position: "sticky", top: 0, background: "#0b0f14" }}>
                <tr style={{ textAlign: "left", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                  <th style={{ padding: "10px 12px", opacity: 0.85, fontWeight: 700 }}>sev</th>
                  <th style={{ padding: "10px 12px", opacity: 0.85, fontWeight: 700 }}>type</th>
                  <th style={{ padding: "10px 12px", opacity: 0.85, fontWeight: 700 }}>canonical_id</th>
                  <th style={{ padding: "10px 12px", opacity: 0.85, fontWeight: 700 }}>message</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ padding: 16, opacity: 0.75 }}>
                      No anomalies detected (or snapshots not loaded yet).
                    </td>
                  </tr>
                ) : (
                  anomalies.map((a, idx) => (
                    <tr
                      key={idx}
                      onClick={() => setSelectedId(a.canonical_id)}
                      style={{ cursor: "pointer", borderBottom: "1px solid rgba(255,255,255,0.06)" }}
                    >
                      <td style={{ padding: "10px 12px", opacity: 0.9, fontWeight: 800 }}>{a.severity}</td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{a.type}</td>
                      <td
                        style={{
                          padding: "10px 12px",
                          fontFamily:
                            "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                          fontSize: 12,
                        }}
                      >
                        {a.canonical_id}
                      </td>
                      <td style={{ padding: "10px 12px", opacity: 0.85 }}>{a.message}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 10, opacity: 0.7, fontSize: 12 }}>
            Total anomalies: {anomalies.length}
          </div>
        </div>
        </div>
      </div>
    </div>
  );
}
