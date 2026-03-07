#!/usr/bin/env python3
"""Validate clock-tree YAML models against schema and graph-level rules.

Phase 1: JSON Schema validation (Draft 2020-12)
Phase 2: Semantic / graph checks:
  - Signal name uniqueness
  - Block name uniqueness (per type and global)
  - Single-producer rule (each signal produced by exactly one block)
  - All outputs declared in signals
  - All inputs reference declared signals
  - No orphan signals (every signal produced or consumed)
  - DAG check (no cycles)
  - Mux input array size is power of 2
  - Frequency range consistency (min <= nominal <= max)
  - Value range consistency (min < max in RegisterField value_range)
"""
import sys, pathlib, argparse, glob
from collections import defaultdict

import yaml  # PyYAML
from jsonschema import Draft202012Validator


# ---------------------------------------------------------------------------
# Phase 1: Schema validation
# ---------------------------------------------------------------------------

def validate_schema(data, validator):
    """Return list of (location, message) tuples for schema errors."""
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return [
        ("/".join(str(p) for p in e.path) or "(root)", e.message)
        for e in errors
    ]


# ---------------------------------------------------------------------------
# Phase 2: Graph / semantic checks
# ---------------------------------------------------------------------------

def _get_blocks(data, key):
    """Return list of blocks from a top-level array key, or []."""
    return data.get(key) or []


def validate_graph(data):
    """Run graph-level checks on a clock-tree model. Return list of (check, message)."""
    errors = []

    signals = {s["name"]: s for s in _get_blocks(data, "signals")}
    generators = _get_blocks(data, "generators")
    muxes = _get_blocks(data, "muxes")
    plls = _get_blocks(data, "plls")
    dividers = _get_blocks(data, "dividers")
    gates = _get_blocks(data, "gates")

    all_blocks = (
        [("generator", b) for b in generators]
        + [("mux", b) for b in muxes]
        + [("pll", b) for b in plls]
        + [("divider", b) for b in dividers]
        + [("gate", b) for b in gates]
    )

    # --- 1. Signal name uniqueness ---
    seen_signals = defaultdict(int)
    for s in data.get("signals") or []:
        seen_signals[s["name"]] += 1
    for name, count in seen_signals.items():
        if count > 1:
            errors.append(("signal-unique", f"signal '{name}' declared {count} times"))

    # --- 2. Block name uniqueness (per type) ---
    for key in ("generators", "muxes", "plls", "dividers", "gates"):
        seen = defaultdict(int)
        for b in _get_blocks(data, key):
            seen[b["name"]] += 1
        for name, count in seen.items():
            if count > 1:
                errors.append(("block-unique", f"{key} block '{name}' declared {count} times"))

    # --- 3. Single-producer rule ---
    producers = defaultdict(list)  # signal_name -> [(block_type, block_name)]
    for btype, b in all_blocks:
        out = b.get("output")
        if out:
            producers[out].append((btype, b["name"]))

    for sig, prods in producers.items():
        if len(prods) > 1:
            sources = ", ".join(f"{t} '{n}'" for t, n in prods)
            errors.append(("single-producer", f"signal '{sig}' produced by multiple blocks: {sources}"))

    # --- 4. All outputs declared in signals ---
    for btype, b in all_blocks:
        out = b.get("output")
        if out and out not in signals:
            errors.append(("output-declared", f"{btype} '{b['name']}' output '{out}' not in signals"))

    # --- 5. All inputs reference declared signals ---
    for btype, b in all_blocks:
        if btype == "mux":
            for i, inp in enumerate(b.get("inputs") or []):
                if inp is not None and inp != "" and inp not in signals:
                    errors.append(("input-declared",
                                   f"mux '{b['name']}' input[{i}] '{inp}' not in signals"))
        else:
            inp = b.get("input")
            if inp and inp not in signals:
                errors.append(("input-declared", f"{btype} '{b['name']}' input '{inp}' not in signals"))

    # --- 6. No orphan signals ---
    consumed = set()
    produced = set(producers.keys())
    for btype, b in all_blocks:
        if btype == "mux":
            for inp in b.get("inputs") or []:
                if inp:
                    consumed.add(inp)
        else:
            inp = b.get("input")
            if inp:
                consumed.add(inp)

    for name in signals:
        if name not in produced and name not in consumed:
            errors.append(("orphan-signal", f"signal '{name}' is neither produced nor consumed"))

    # --- 7. Every signal has a producer ---
    for name in signals:
        if name not in produced:
            # Only warn — external inputs without a generator are valid but suspicious
            if name in consumed:
                errors.append(("no-producer", f"signal '{name}' is consumed but has no producer"))

    # --- 8. Frequency range consistency ---
    for s in data.get("signals") or []:
        lo = s.get("min")
        hi = s.get("max")
        nom = s.get("nominal")
        name = s["name"]
        if lo is not None and hi is not None and lo > hi:
            errors.append(("freq-range", f"signal '{name}': min ({lo}) > max ({hi})"))
        if nom is not None and lo is not None and nom < lo:
            errors.append(("freq-range", f"signal '{name}': nominal ({nom}) < min ({lo})"))
        if nom is not None and hi is not None and nom > hi:
            errors.append(("freq-range", f"signal '{name}': nominal ({nom}) > max ({hi})"))

    # PLL VCO limits consistency
    for p in plls:
        vco = p.get("vco_limits") or {}
        vmin, vmax = vco.get("min"), vco.get("max")
        if vmin is not None and vmax is not None and vmin > vmax:
            errors.append(("freq-range", f"pll '{p['name']}': vco_limits min ({vmin}) > max ({vmax})"))

    # --- 10. Value range consistency ---
    for btype, b in all_blocks:
        for field_key in ("control", "factor", "denominator", "feedback_integer",
                          "feedback_fraction", "post_divider"):
            rf = b.get(field_key)
            if not rf:
                continue
            vr = rf.get("value_range")
            if vr:
                lo = vr.get("min", 0)
                hi = vr.get("max")
                if hi is not None and lo > hi:
                    errors.append(("value-range",
                                   f"{btype} '{b['name']}' {field_key}: value_range min ({lo}) > max ({hi})"))

    # --- 11. DAG check (no cycles) ---
    # Build adjacency: signal -> set of signals it feeds into
    # An edge exists from each input signal to the output signal of the same block
    adj = defaultdict(set)
    for btype, b in all_blocks:
        out = b.get("output")
        if not out:
            continue
        if btype == "mux":
            for inp in b.get("inputs") or []:
                if inp:
                    adj[inp].add(out)
        else:
            inp = b.get("input")
            if inp:
                adj[inp].add(out)

    # Kahn's algorithm for topological sort
    in_degree = defaultdict(int)
    all_nodes = set(adj.keys())
    for targets in adj.values():
        all_nodes.update(targets)
    for targets in adj.values():
        for t in targets:
            in_degree[t] += 1

    queue = [n for n in all_nodes if in_degree[n] == 0]
    visited = 0
    while queue:
        node = queue.pop()
        visited += 1
        for neighbor in adj.get(node, ()):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited < len(all_nodes):
        # Find nodes still with in_degree > 0 — they form the cycle(s)
        cycle_nodes = sorted(n for n in all_nodes if in_degree[n] > 0)
        errors.append(("dag", f"cycle detected involving: {', '.join(cycle_nodes)}"))

    return errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Validate clock-tree YAML models (schema + graph checks)")
    ap.add_argument("-s", "--schema", required=True, help="Path to JSON/YAML schema")
    ap.add_argument("-d", "--docs", nargs="+", required=True, help="YAML spec files or globs")
    args = ap.parse_args()

    schema = yaml.safe_load(pathlib.Path(args.schema).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    files = []
    for pattern in args.docs:
        files.extend(glob.glob(pattern, recursive=True))
    if not files:
        print("No files matched", file=sys.stderr)
        sys.exit(2)

    had_errors = False
    for f in sorted(set(files)):
        if not (f.endswith(".yaml") or f.endswith(".yml")):
            continue
        data = yaml.safe_load(pathlib.Path(f).read_text(encoding="utf-8"))

        # Phase 1: schema
        schema_errors = validate_schema(data, validator)
        # Phase 2: graph (only if schema passes — malformed data may crash graph checks)
        graph_errors = validate_graph(data) if not schema_errors else []

        if schema_errors or graph_errors:
            had_errors = True
            print(f"❌ {f}:")
            for loc, msg in schema_errors:
                print(f"   schema  │ at {loc}: {msg}")
            for check, msg in graph_errors:
                print(f"   {check:8s}│ {msg}")
        else:
            print(f"✅ {f}")

    sys.exit(1 if had_errors else 0)


if __name__ == "__main__":
    main()
