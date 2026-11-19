"""Watch one game move by move, or play one yourself.

    python play.py mixed builder --seed 3
    python play.py random mixed_save --seed 10 --board-every 5
    python play.py human mixed_save          # you move first, as X
    python play.py counter human --seed 7    # you move second, as O

X is the first player (moves first), O is the second. Any game in a tournament CSV
can be replayed with its two bots and its seed (plus --values or
--sequences-to-win if the tournament used them).
"""

import argparse

from board import CELL_CARD, JACKS, TWO_EYED_JACKS, pretty, row_col
from bots import make_bot
from game import play_game
from scoring import VALUE_SCALES


def describe(move, traded):
    note = f"  (traded in dead card {pretty(traded)})" if traded else ""
    if move is None:
        return "passes (no legal move)" + note
    r, c = row_col(move.cell)
    if move.remove:
        return f"plays {pretty(move.card)}, removes the chip on {pretty(CELL_CARD[move.cell])} at ({r},{c})" + note
    return f"plays {pretty(move.card)} on {pretty(CELL_CARD[move.cell])} at ({r},{c})" + note


def numbered(board_text):
    """Add row and column numbers to Game.render() output."""
    header = "    " + " ".join(f"{c:^3}" for c in range(10))
    rows = [f"{r:>2}  {line}" for r, line in enumerate(board_text.splitlines())]
    return "\n".join([header] + rows)


class HumanBot:
    """You play: the board and your hand are shown, then you type a move."""

    def __init__(self, name="human"):
        self.name = name

    def choose(self, view, p, moves, rng):
        marks = "XO"
        print(f"\nYou are {marks[p]}. Chips in a completed sequence are shown as [X] or [O].\n")
        print(numbered(view.render(marks)))
        print("\nYour hand: " + "  ".join(pretty(card) for card in sorted(view.hand)))
        normal = [m for m in moves if m.card not in JACKS]
        wild = {m.cell: m for m in moves if m.card in TWO_EYED_JACKS}
        removal = {m.cell: m for m in moves if m.remove}
        for i, move in enumerate(normal, 1):
            r, c = row_col(move.cell)
            print(f"  {i:>3}. {pretty(move.card)} on ({r},{c})")
        if wild:
            print("  w ROW COL   two-eyed Jack: put a chip on any open space")
        if removal:
            print("  r ROW COL   one-eyed Jack: remove an opponent chip that isn't in a sequence")
        while True:
            words = input("Your move (q to quit): ").strip().lower().split()
            if not words:
                continue
            if words[0] in ("q", "quit"):
                raise SystemExit("Game abandoned.")
            if len(words) == 1 and words[0].isdigit() and 1 <= int(words[0]) <= len(normal):
                return normal[int(words[0]) - 1]
            if (len(words) == 3 and words[0] in ("w", "r") and words[1].isdigit()
                    and words[2].isdigit() and int(words[1]) < 10 and int(words[2]) < 10):
                options = wild if words[0] == "w" else removal
                cell = int(words[1]) * 10 + int(words[2])
                if cell in options:
                    return options[cell]
            print("That isn't one of the moves listed. Try again.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Watch or play one game of Sequence.")
    parser.add_argument("first", help="bot that moves first (X), or 'human'")
    parser.add_argument("second", help="bot that moves second (O), or 'human'")
    parser.add_argument("--seed", type=int, default=1, help="which deal to play")
    parser.add_argument("--board-every", type=int, default=0, metavar="N",
                        help="also print the board every N turns")
    parser.add_argument("--values", choices=sorted(VALUE_SCALES),
                        help="line-value scale for heuristic bots (as in tournament.py)")
    parser.add_argument("--sequences-to-win", type=int, default=2)
    parser.add_argument("--max-turns", type=int, default=500)
    args = parser.parse_args(argv)

    bots = tuple(HumanBot() if spec == "human" else make_bot(spec, args.values)
                 for spec in (args.first, args.second))
    marks = "XO"
    seen = [0, 0]

    def observer(game, p, move):
        _, _, traded = game.history[-1]
        print(f"{game.turn:3d}. {marks[p]} {bots[p].name:<12} {describe(move, traded)}")
        for seq in game.sequences[p][seen[p]:]:
            print(f"     {marks[p]} completes a sequence: {[row_col(c) for c in seq]}")
        seen[p] = len(game.sequences[p])
        if args.board_every and game.turn % args.board_every == 0:
            print("\n" + numbered(game.render(marks)) + "\n")

    game = play_game(bots[0], bots[1], args.seed, max_turns=args.max_turns, observer=observer,
                     sequences_to_win=args.sequences_to_win)
    print("\n" + numbered(game.render(marks)) + "\n")
    if game.winner is None:
        print(f"Draw after {game.turn} turns.")
    else:
        print(f"{marks[game.winner]} ({bots[game.winner].name}) wins after {game.turn} turns.")


if __name__ == "__main__":
    main()
