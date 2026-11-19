"""Counter-strategy hunt (the double oracle method): can anything beat the equilibrium?

    python hunt.py                                        # start from the pilot champion
    python hunt.py --pool mixed_save counter adaptive --iterations 6
    python hunt.py --screen-deals 50 --confirm-deals 400  # quicker and rougher

Each iteration:
  1. Solve the meta-game of the current pool: its Nash equilibrium mix.
  2. Screen candidates against that mix on a few deals. The candidates are every
     one-setting change of the bots in the mix, plus some random settings.
  3. Confirm the best few on fresh deals, so a lucky screening result can't win
     (the "winner's curse" of picking the best of many noisy estimates).
  4. If the best confirmed candidate beats the mix beyond the noise (its 95%
     interval lies above 50%), add it to the pool and repeat. Otherwise stop:
     nothing found beats the equilibrium.

The search space is HeuristicBot's settings (SPACE below). Results go to --out:
hunt_log.md (what happened at each iteration), pool_matrix.csv (the final pool's
win rates) and games.csv (every game played, in the tournament format). To analyse
the final pool properly, rerun it as a tournament with the command printed at the end.

References: McMahan, Gordon & Blum (2003), the double oracle; Lanctot et al. (2017),
PSRO, its generalisation.
"""

import argparse
import csv
import itertools
import math
import os
import random

import numpy as np
import pandas as pd

from analysis import Z, equilibrium
from bots import heuristic_settings, make_bot
from tournament import FIELDS, run_jobs

# The settings the hunt may change, and the values it tries for each.
SPACE = {
    "attack": [0.5, 1.0, 1.5, 2.0],
    "defend": [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0],
    "jacks": ["greedy", "save", "save_wild", "save_remove", "eager"],
    "values": ["linear", "flat", "default", "steep"],
    "center": [0.0, 5.0, 10.0, 20.0],
    "fork": [0.0, 0.5, 1.0, 2.0],
    "hand": [0.0, 1.0],
    "count": [0, 1],
    "infer": [0, 1],
    "mode": ["fixed", "adapt", "phase", "read"],  # at most one way of moving the weights
}
DEFAULTS = {"attack": 1.0, "defend": 1.0, "jacks": "greedy", "values": "default",
            "center": 0.0, "fork": 0.0, "hand": 0.0, "count": 0, "infer": 0,
            "mode": "fixed", "lam": 0.0}
ORDER = ["attack", "defend", "jacks", "values", "center", "fork", "hand", "count",
         "infer", "mode", "lam"]


# ---- the search space -------------------------------------------------------------

def settings_of(spec):
    """A heuristic spec's settings in the hunt's terms (`mode` instead of three flags)."""
    s = dict(DEFAULTS)
    for key, value in heuristic_settings(spec).items():
        if key in ("adapt", "phase", "read"):
            if value:
                s["mode"] = key
        else:
            s[key] = value
    return s


def spec_of(s):
    """The canonical spec for settings: 'mixed' plus every non-default setting."""
    parts = []
    for key in ORDER:
        value = s[key]
        if value == DEFAULTS[key]:
            continue
        if key == "mode":
            parts.append(f"{value}=1")
        elif isinstance(value, float):
            parts.append(f"{key}={value:g}")
        else:
            parts.append(f"{key}={value}")
    return "mixed" + (":" + ",".join(parts) if parts else "")


def canon(spec):
    """Canonical form of any spec, so 'mixed_save' and 'mixed:jacks=save' count as one."""
    try:
        return spec_of(settings_of(spec))
    except ValueError:  # not a heuristic bot, e.g. random or sampler
        return spec


def _fix(s):
    if s["infer"]:
        s["count"] = 1
    return s


def neighbors(s):
    """Every setting that differs from `s` in exactly one place."""
    for key, options in SPACE.items():
        for option in options:
            if option != s[key]:
                t = dict(s)
                t[key] = option
                if key == "count" and not option:
                    t["infer"] = 0
                yield _fix(t)


def random_settings(rng):
    s = {key: rng.choice(options) for key, options in SPACE.items()}
    s["lam"] = 0.0
    return _fix(s)


# ---- playing and scoring ----------------------------------------------------------

class Arena:
    """Plays the hunt's games on fresh deals and logs them all to one CSV."""

    def __init__(self, workers, writer, first_seed, max_turns):
        self.workers = workers
        self.writer = writer
        self.next_seed = first_seed
        self.next_id = 0
        self.max_turns = max_turns
        self.games = 0

    def play(self, pairs, deals):
        """Play every (a, b) pair on `deals` fresh deals, both seatings.

        Returns {(a, b): (a's mean score, its standard error)}, computed over deals."""
        seeds = list(range(self.next_seed, self.next_seed + deals))
        self.next_seed += deals
        oriented = {frozenset(pair): pair for pair in pairs}
        jobs = []
        for a, b in oriented.values():
            for seed in seeds:
                jobs.append((self.next_id, a, b, seed, self.max_turns))
                jobs.append((self.next_id + 1, b, a, seed, self.max_turns))
                self.next_id += 2
        totals = {pair: dict.fromkeys(seeds, 0.0) for pair in oriented.values()}

        def on_row(row):
            self.writer.writerow(row)
            a, b = oriented[frozenset((row["seat0"], row["seat1"]))]
            score = 0.5 if row["winner"] == "draw" else float(row["winner"] == a)
            totals[(a, b)][row["seed"]] += score

        run_jobs(jobs, self.workers, on_row)
        self.games += len(jobs)
        results = {}
        for pair, per_seed in totals.items():
            scores = np.array(list(per_seed.values())) / 2.0
            se = scores.std(ddof=1) / math.sqrt(len(scores)) if len(scores) > 1 else 0.5
            results[pair] = (float(scores.mean()), float(se))
        return results


def payoff(results, candidate, support, weights):
    """The candidate's expected score against the equilibrium mix, and its standard error."""
    value = sum(w * results[(candidate, s)][0] for s, w in zip(support, weights))
    se = math.sqrt(sum((w * results[(candidate, s)][1]) ** 2 for s, w in zip(support, weights)))
    return value, se


def pool_matrix(pool, stats):
    M = pd.DataFrame(0.5, index=pool, columns=pool)
    for a, b in itertools.combinations(pool, 2):
        mean = stats[(a, b)][0] if (a, b) in stats else 1.0 - stats[(b, a)][0]
        M.loc[a, b], M.loc[b, a] = mean, 1.0 - mean
    return M


def solve(pool, stats):
    if len(pool) == 1:
        return pd.Series([1.0], index=pool)
    mix, _ = equilibrium(pool_matrix(pool, stats))
    return mix


def _mix_text(mix):
    return ", ".join(f"{b} {100 * w:.0f}%" for b, w in mix.items() if w > 0.01)


# ---- the hunt ------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description="Search for strategies that beat the equilibrium.")
    parser.add_argument("--pool", nargs="+", default=["mixed_save"], help="starting pool (default: mixed_save)")
    parser.add_argument("--iterations", type=int, default=6)
    parser.add_argument("--screen-deals", type=int, default=100, help="deals per candidate and opponent when screening")
    parser.add_argument("--confirm-deals", type=int, default=1000, help="deals per pairing when confirming")
    parser.add_argument("--finalists", type=int, default=3, help="screened candidates to confirm")
    parser.add_argument("--random", type=int, default=12, help="random candidates per iteration")
    parser.add_argument("--seed", type=int, default=900_000, help="first deal's seed; also seeds the random candidates")
    parser.add_argument("--max-turns", type=int, default=500)
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--out", default=os.path.join("results", "hunt"))
    args = parser.parse_args(argv)

    pool = list(dict.fromkeys(args.pool))
    for spec in pool:
        try:
            make_bot(spec)
        except ValueError as err:
            parser.error(str(err))
    os.makedirs(args.out, exist_ok=True)
    rng = random.Random(args.seed)
    log = ["# Counter-strategy hunt", "",
           f"Start pool: {', '.join(pool)}. Screening on {args.screen_deals} deals, "
           f"confirming on {args.confirm_deals} fresh deals per pairing.", ""]

    def save_log():
        with open(os.path.join(args.out, "hunt_log.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")

    with open(os.path.join(args.out, "games.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        arena = Arena(args.workers, writer, args.seed, args.max_turns)
        stats = {}
        if len(pool) > 1:
            print(f"Playing the starting pool ({len(pool)} bots)...")
            stats.update(arena.play(list(itertools.combinations(pool, 2)), args.confirm_deals))

        for iteration in range(1, args.iterations + 1):
            mix = solve(pool, stats)
            support = [b for b in pool if mix[b] > 0.01]
            weights = np.array([mix[b] for b in support])
            weights = weights / weights.sum()
            taken = {canon(b) for b in pool}
            candidates = {}
            for b in support:
                try:
                    base = settings_of(b)
                except ValueError:
                    continue
                for s in neighbors(base):
                    candidates.setdefault(spec_of(s), True)
            for _ in range(args.random):
                candidates.setdefault(spec_of(random_settings(rng)), True)
            candidates = [c for c in candidates if c not in taken]
            if not candidates:
                log += [f"## Iteration {iteration}", "", "No untried candidates left. Stopping.", ""]
                save_log()
                break
            print(f"\nIteration {iteration}: equilibrium {_mix_text(mix)}; "
                  f"screening {len(candidates)} candidates...")

            screen = arena.play([(c, s) for c in candidates for s in support], args.screen_deals)
            estimate = {c: payoff(screen, c, support, weights)[0] for c in candidates}
            finalists = sorted(candidates, key=lambda c: -estimate[c])[:args.finalists]
            print(f"  confirming {', '.join(finalists)}...")
            confirm = arena.play([(c, s) for c in finalists for s in support], args.confirm_deals)
            confirmed = {c: payoff(confirm, c, support, weights) for c in finalists}
            best = max(finalists, key=lambda c: confirmed[c][0])
            value, se = confirmed[best]
            low, high = value - Z * se, value + Z * se

            log += [f"## Iteration {iteration}", "",
                    f"Pool: {', '.join(pool)}", "", f"Equilibrium: {_mix_text(mix)}", "",
                    f"Screened {len(candidates)} candidates on {args.screen_deals} deals each. Finalists:", "",
                    "| candidate | screening estimate | confirmed vs the mix | 95% interval |", "|---|---|---|---|"]
            for c in finalists:
                v, e = confirmed[c]
                log.append(f"| {c} | {100 * estimate[c]:.1f}% | {100 * v:.1f}% | "
                           f"{100 * (v - Z * e):.1f}% to {100 * (v + Z * e):.1f}% |")
            log.append("")
            if low <= 0.5:
                log += [f"Best: {best}, {100 * value:.1f}% ({100 * low:.1f}% to {100 * high:.1f}%). "
                        "Its interval includes 50%, so nothing found beats the equilibrium. Stopping.", ""]
                save_log()
                print(f"  best {best}: {100 * value:.1f}%, not beyond the noise. Stopping.")
                break
            log += [f"Added **{best}**: it beats the mix {100 * value:.1f}% of the time "
                    f"({100 * low:.1f}% to {100 * high:.1f}%).", ""]
            save_log()
            print(f"  added {best}: {100 * value:.1f}% against the mix")
            pool.append(best)
            for s in support:
                stats[(best, s)] = confirm[(best, s)]
            rest = [b for b in pool if b != best and b not in support]
            if rest:
                stats.update(arena.play([(best, b) for b in rest], args.confirm_deals))

    mix = solve(pool, stats)
    M = pool_matrix(pool, stats)
    M.to_csv(os.path.join(args.out, "pool_matrix.csv"))
    command = (f"python tournament.py --bots {' '.join(pool)} --deals 2000 "
               f"--out {os.path.join(args.out, 'final_pool', 'games.csv')}")
    log += ["## Final pool", "", f"Pool: {', '.join(pool)}", "", f"Equilibrium: {_mix_text(mix)}", "",
            f"Games played: {arena.games:,}", "", "For a full analysis of the final pool, run:", "",
            f"    {command}", ""]
    save_log()
    print(f"\nFinal equilibrium: {_mix_text(mix)}")
    print(f"{arena.games:,} games played. Log: {os.path.join(args.out, 'hunt_log.md')}")
    print(f"Next: {command}")


if __name__ == "__main__":
    main()
