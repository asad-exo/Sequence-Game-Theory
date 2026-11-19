"""Board layout, cards and the 192 five-in-a-row lines of a Sequence board.

Cells are numbered 0-99, row by row: cell = row * 10 + col.

Run `python board.py` to print the layout and compare it with a physical board.
"""

SIZE = 10
FREE = "XX"  # the four corners are free spaces that count as a chip for every player

# Standard Sequence board, row by row ("T" = ten). If your physical board differs,
# edit this; validate_layout() refuses to run if a card is missing or duplicated.
LAYOUT = (
    "XX 2S 3S 4S 5S 6S 7S 8S 9S XX",
    "6C 5C 4C 3C 2C AH KH QH TH TS",
    "7C AS 2D 3D 4D 5D 6D 7D 9H QS",
    "8C KS 6C 5C 4C 3C 2C 8D 8H KS",
    "9C QS 7C 6H 5H 4H AH 9D 7H AS",
    "TC TS 8C 7H 2H 3H KH TD 6H 2D",
    "QC 9S 9C 8H 9H TH QH QD 5H 3D",
    "KC 8S TC QC KC AC AD KD 4H 4D",
    "AC 7S 6S 5S 4S 3S 2S 2H 3H 5D",
    "XX AD KD QD TD 9D 8D 7D 6D XX",
)

RANKS = "A23456789TJQK"
SUITS = "SHDC"
TWO_EYED_JACKS = frozenset({"JD", "JC"})  # wild: place a chip on any open space
ONE_EYED_JACKS = frozenset({"JS", "JH"})  # remove one opponent chip (not from a sequence)
JACKS = TWO_EYED_JACKS | ONE_EYED_JACKS


def full_deck():
    """Two standard 52-card decks: 104 cards, 8 of them Jacks."""
    return [rank + suit for rank in RANKS for suit in SUITS] * 2


CELL_CARD = tuple(label for row in LAYOUT for label in row.split())
IS_CORNER = tuple(label == FREE for label in CELL_CARD)
CORNERS = tuple(cell for cell, corner in enumerate(IS_CORNER) if corner)


def _card_cells():
    cells = {}
    for cell, label in enumerate(CELL_CARD):
        if label != FREE:
            cells.setdefault(label, []).append(cell)
    return {card: tuple(spots) for card, spots in cells.items()}


CARD_CELLS = _card_cells()  # card -> its two cells, e.g. "7H" -> (48, 53)


def _build_lines():
    """Every run of 5 cells in a row: horizontal, vertical and both diagonals."""
    directions = ((0, 1), (1, 0), (1, 1), (1, -1))
    lines = []
    for r in range(SIZE):
        for c in range(SIZE):
            for dr, dc in directions:
                if 0 <= r + 4 * dr < SIZE and 0 <= c + 4 * dc < SIZE:
                    lines.append(tuple((r + k * dr) * SIZE + c + k * dc for k in range(5)))
    return tuple(lines)


LINES = _build_lines()  # 60 horizontal + 60 vertical + 72 diagonal = 192
LINES_THROUGH = tuple(
    tuple(i for i, line in enumerate(LINES) if cell in line) for cell in range(SIZE * SIZE)
)
LINE_CORNERS = tuple(sum(IS_CORNER[cell] for cell in line) for line in LINES)


def validate_layout():
    """Raise ValueError unless every non-Jack card appears exactly twice."""
    problems = []
    if len(LAYOUT) != SIZE or any(len(row.split()) != SIZE for row in LAYOUT):
        problems.append("the layout must be 10 rows of 10 spaces")
    if CORNERS != (0, SIZE - 1, SIZE * (SIZE - 1), SIZE * SIZE - 1):
        problems.append(f"free spaces must be the four corners, found at {CORNERS}")
    expected = {rank + suit for rank in RANKS if rank != "J" for suit in SUITS}
    for card in sorted(expected):
        count = len(CARD_CELLS.get(card, ()))
        if count != 2:
            problems.append(f"{card} appears {count} times (should be 2)")
    for card in sorted(set(CARD_CELLS) - expected):
        problems.append(f"unexpected label {card!r} on the board")
    if problems:
        raise ValueError("Bad board layout:\n  " + "\n  ".join(problems))


validate_layout()

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}


def pretty(card):
    """'TH' -> '10♥'. Corners become '★'."""
    if card == FREE:
        return "★"
    rank = "10" if card[0] == "T" else card[0]
    return rank + SUIT_SYMBOLS[card[1]]


def row_col(cell):
    return divmod(cell, SIZE)


if __name__ == "__main__":
    print("Sequence board (row 0 at the top). Compare with your physical board:\n")
    for row in LAYOUT:
        print("  " + " ".join(f"{pretty(label):>3}" for label in row.split()))
    print(f"\n{len(LINES)} five-in-a-row lines; every card appears exactly twice.")
