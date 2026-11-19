"""Round-robin tournament between bots, logged game by game to a CSV.

    python tournament.py --deals 1000                    # all 18 fast strategies
    python tournament.py --roster pilot --deals 5000 --out results/full_run/games.csv
    python tournament.py --roster jacks --deals 2000 --out results/jacks/games.csv
    python tournament.py --bots mixed_save mixed_save:defend=0.5 counter --deals 500
    python tournament.py --roster pilot --values steep --out results/values_steep/games.csv
    python tournament.py --roster pilot --sequences-to-win 1 --out results/one_sequence/games.csv

Design:
- Duplicate format: every deal (seed) is played twice for each pair of bots,
  once with each bot moving first, so neither bot benefits from a lucky deal.
- Mirror matches (a bot against a copy of itself) are played on 2 x deals
  different deals; they measure the first-move advantage.
- Every game is reproducible from its seed: `python play.py A B --seed S`.
- The settings of the run are saved next to the CSV (games_run.json).
"""

import argparse
import csv
import itertools
import json
import os
import platform
import sys
import time

from bots import DEFAULT_BOTS, ROSTERS, make_bot
from game import play_game
from scoring import VALUE_SCALES

FIELDS = [
    "game_id", "seed", "seat0", "seat1", "mirror", "winner_seat", "winner", "turns",
    "seqs0", "seqs1", "two_eyed0", "two_eyed1", "one_eyed0", "one_eyed1",
    "dead_swaps0", "dead_swaps1", "passes0", "passes1", "reshuffles",
    "jack_finish0", "jack_finish1", "jack_block0", "jack_block1", "jack_break0", "jack_break1",
]


def schedule(bots, deals, base_seed=2026):
    """All games to play, as (game_id, seat0, seat1, seed) tuples."""
    games = []
    for a, b in itertools.combinations(bots, 2):
        for d in range(deals):
            games.append((a, b, base_seed + d))
            games.append((b, a, base_seed + d))
    for a in bots:
        for d in range(2 * deals):
            games.append((a, a, base_seed + d))
    return [(i, *g) for i, g in enumerate(games)]


def encode_sequences(sequences):
    """[(1,2,3,4,5), (5,15,25,35,45)] -> '1-2-3-4-5;5-15-25-35-45'"""
    return ";".join("-".join(map(str, seq)) for seq in sequences)


def record(game_id, seat0, seat1, seed, game):
    w = game.winner
    return {
        "game_id": game_id, "seed": seed, "seat0": seat0, "seat1": seat1,
        "mirror": int(seat0 == seat1),
        "winner_seat": -1 if w is None else w,
        "winner": "draw" if w is None else (seat0, seat1)[w],
        "turns": game.turn,
        "seqs0": encode_sequences(game.sequences[0]),
        "seqs1": encode_sequences(game.sequences[1]),
        "two_eyed0": game.two_eyed_used[0], "two_eyed1": game.two_eyed_used[1],
        "one_eyed0": game.one_eyed_used[0], "one_eyed1": game.one_eyed_used[1],
        "dead_swaps0": game.dead_swaps[0], "dead_swaps1": game.dead_swaps[1],
        "passes0": game.passes[0], "passes1": game.passes[1],
        "reshuffles": game.reshuffles,
        "jack_finish0": game.jack_finishes[0], "jack_finish1": game.jack_finishes[1],
        "jack_block0": game.jack_blocks[0], "jack_block1": game.jack_blocks[1],
        "jack_break0": game.jack_breaks[0], "jack_break1": game.jack_breaks[1],
    }


_bot_cache = {}


def _bot(spec, values=None):
    key = (spec, values)
    if key not in _bot_cache:
        _bot_cache[key] = make_bot(spec, values)
    return _bot_cache[key]


def run_game(job):
    """Play one scheduled game. job = (game_id, seat0, seat1, seed, max_turns[, values[, sequences_to_win]])."""
    game_id, seat0, seat1, seed, max_turns, *extra = job
    values = extra[0] if len(extra) > 0 else None
    sequences_to_win = extra[1] if len(extra) > 1 else 2
    game = play_game(_bot(seat0, values), _bot(seat1, values), seed, max_turns=max_turns,
                     sequences_to_win=sequences_to_win)
    return record(game_id, seat0, seat1, seed, game)


def run_jobs(jobs, workers, on_row):
    """Run game jobs on `workers` processes, calling on_row(row) for each result in order."""
    if workers > 1:
        from multiprocessing import Pool
        with Pool(workers) as pool:
            chunk = max(1, len(jobs) // (workers * 50))
            for row in pool.imap(run_game, jobs, chunksize=chunk):
                on_row(row)
    else:
        for job in jobs:
            on_row(run_game(job))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Round-robin Sequence tournament.")
    parser.add_argument("--roster", choices=sorted(ROSTERS), default="full",
                        help="named group of bots (default: full, the 18 fast strategies)")
    parser.add_argument("--bots", nargs="+",
                        help="bot specs instead of a roster, e.g. random mixed_save mixed:defend=0.5")
    parser.add_argument("--deals", type=int, default=1000,
                        help="deals per pairing; each is played twice (default: %(default)s)")
    parser.add_argument("--seed", type=int, default=2026, help="first deal's seed (default: %(default)s)")
    parser.add_argument("--values", choices=sorted(VALUE_SCALES),
                        help="line-value scale for every heuristic bot whose spec doesn't set one")
    parser.add_argument("--sequences-to-win", type=int, default=2,
                        help="rule variant: sequences needed to win (default: %(default)s)")
    parser.add_argument("--max-turns", type=int, default=500, help="plies before a game is a draw")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 1,
                        help="parallel processes (default: all cores)")
    parser.add_argument("--out", default=os.path.join("results", "games.csv"))
    args = parser.parse_args(argv)

    bots = args.bots or (DEFAULT_BOTS if args.roster == "full" else ROSTERS[args.roster])
    if len(set(bots)) != len(bots):
        parser.error("each bot may appear only once")
    for spec in bots:
        try:
            make_bot(spec, args.values)
        except ValueError as err:
            parser.error(str(err))
    if args.sequences_to_win < 1:
        parser.error("--sequences-to-win must be at least 1")

    jobs = [(*g, args.max_turns, args.values, args.sequences_to_win)
            for g in schedule(bots, args.deals, args.seed)]
    pairs = len(bots) * (len(bots) - 1) // 2
    print(f"{len(jobs):,} games: {pairs} pairings x {2 * args.deals:,} games, "
          f"plus {len(bots)} mirror matches x {2 * args.deals:,} games, on {args.workers} worker(s)")
    if args.values or args.sequences_to_win != 2:
        print(f"Variant: line values = {args.values or 'per bot'}, "
              f"sequences to win = {args.sequences_to_win}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    info = {
        "bots": bots, "deals": args.deals, "seed": args.seed, "values": args.values,
        "sequences_to_win": args.sequences_to_win, "max_turns": args.max_turns,
        "games": len(jobs), "python": platform.python_version(),
        "command": "python tournament.py " + " ".join(sys.argv[1:] if argv is None else argv),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.splitext(args.out)[0] + "_run.json", "w") as f:
        json.dump(info, f, indent=2)

    start = time.time()
    step = max(1, len(jobs) // 20)
    done = 0
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        def on_row(row):
            nonlocal done
            writer.writerow(row)
            done += 1
            if done % step == 0 or done == len(jobs):
                elapsed = time.time() - start
                eta = elapsed / done * (len(jobs) - done)
                print(f"  {done:>9,} / {len(jobs):,} games   {elapsed:6.0f}s elapsed, ~{eta:.0f}s left",
                      flush=True)

        run_jobs(jobs, args.workers, on_row)
    print(f"Saved {args.out} in {time.time() - start:.0f}s. Next: python analysis.py {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
