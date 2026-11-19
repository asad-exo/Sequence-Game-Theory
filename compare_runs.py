"""Compare two tournament runs.

    python compare_runs.py results/pilot/games.csv.gz results/replication/games.csv
    python compare_runs.py results/pilot/games.csv.gz results/values_steep/games.csv

Use it for a replication (same bots on fresh deals: every difference should look
like chance) or a sensitivity check (same bots under other line values or rules:
did the ranking or the equilibrium change?). Prints a report and saves
comparison.md next to the second CSV.
"""

import argparse
import itertools
import os

import numpy as np
import pandas as pd

import analysis


def _pct(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{100 * x:.1f}%"


def _table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def pairing_differences(Ma, Ha, Mb, Hb, bots):
    """One row per pairing: win rate in each run, the difference (B - A), its z, and
    whether it is beyond chance (|z| >= 1.96). The runs are treated as independent."""
    rows = []
    for a, b in itertools.combinations(bots, 2):
        se = float(np.hypot(Ha.loc[a, b], Hb.loc[a, b])) / analysis.Z
        diff = float(Mb.loc[a, b] - Ma.loc[a, b])
        z = diff / se if se > 0 else float("nan")
        rows.append({"a": a, "b": b, "rate_a": float(Ma.loc[a, b]), "margin_a": float(Ha.loc[a, b]),
                     "rate_b": float(Mb.loc[a, b]), "margin_b": float(Hb.loc[a, b]), "diff": diff,
                     "z": z, "beyond": bool(np.isfinite(z) and abs(z) >= analysis.Z)})
    return pd.DataFrame(rows)


def compare(path_a, path_b):
    """The comparison report as Markdown."""
    games_a, games_b = analysis.load_games(path_a), analysis.load_games(path_b)
    in_b = set(analysis.bot_order(games_b))
    bots = [b for b in analysis.bot_order(games_a) if b in in_b]
    if len(bots) < 2:
        raise SystemExit("The two runs share fewer than two bots, so there is nothing to compare.")
    Ma, Ha, _ = analysis.win_matrix(games_a, bots)
    Mb, Hb, _ = analysis.win_matrix(games_b, bots)

    out = ["# Comparison of two runs", "", f"- Run A: `{path_a}`", f"- Run B: `{path_b}`", ""]
    diffs = pairing_differences(Ma, Ha, Mb, Hb, bots)
    flagged = int(diffs["beyond"].sum())
    rows = [[f"{r.a} vs {r.b}", f"{_pct(r.rate_a)} ±{100 * r.margin_a:.1f}",
             f"{_pct(r.rate_b)} ±{100 * r.margin_b:.1f}", f"{100 * r.diff:+.1f}",
             f"{r.z:+.2f}" if np.isfinite(r.z) else "n/a",
             "beyond chance" if r.beyond else "within chance"] for r in diffs.itertuples()]
    pairs = len(rows)
    out += ["## Win rates", "",
            "Row bot's win rate against the column bot in each run. z is the difference divided "
            "by its standard error; |z| of 1.96 or more is beyond what chance usually explains.", "",
            _table(["pairing", "run A", "run B", "B - A (points)", "z", "verdict"], rows), "",
            f"{flagged} of {pairs} differences are beyond chance; about {0.05 * pairs:.1f} would "
            "be expected by luck alone if nothing had changed."]

    mix_a, _ = analysis.equilibrium(Ma)
    mix_b, _ = analysis.equilibrium(Mb)
    avg_a = {b: Ma.loc[b, [o for o in bots if o != b]].mean() for b in bots}
    avg_b = {b: Mb.loc[b, [o for o in bots if o != b]].mean() for b in bots}
    rank_a = sorted(bots, key=lambda b: -avg_a[b])
    rank_b = sorted(bots, key=lambda b: -avg_b[b])
    out += ["", "## Rankings and equilibrium", "",
            _table(["bot", "avg vs field A", "avg vs field B", "equilibrium A", "equilibrium B"],
                   [[b, _pct(avg_a[b]), _pct(avg_b[b]), _pct(mix_a[b]), _pct(mix_b[b])] for b in bots]),
            "", "Ranking A: " + " > ".join(rank_a), "", "Ranking B: " + " > ".join(rank_b), "",
            "The rankings are " + ("identical." if rank_a == rank_b else "different.")]

    fm_a, fm_b = analysis.first_move(games_a, bots), analysis.first_move(games_b, bots)
    labels = [label for label in fm_a.index if label in fm_b.index]
    out += ["", "## First-move advantage", "",
            _table(["games", "run A", "run B"],
                   [[label, _pct(fm_a.loc[label, "first_player_win_rate"]),
                     _pct(fm_b.loc[label, "first_player_win_rate"])] for label in labels])]
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two tournament CSVs.")
    parser.add_argument("run_a", help="the reference run, e.g. results/pilot/games.csv.gz")
    parser.add_argument("run_b", help="the run to compare with it")
    parser.add_argument("--out", help="where to save the report (default: comparison.md next to run_b)")
    args = parser.parse_args(argv)
    report = compare(args.run_a, args.run_b)
    path = args.out or os.path.join(os.path.dirname(args.run_b) or ".", "comparison.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
