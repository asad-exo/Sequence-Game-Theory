"""How the heuristic strategies value a move.

Everything is measured on the 192 five-in-a-row lines. For a chip on space `cell`:
  gain   how much the move strengthens the mover's open lines through `cell`
  block  how much it weakens the opponent's open lines through `cell`
An open line has no opponent chips and can still become a new sequence. Its value
grows steeply with the spaces that count for its owner (chips plus corners).

The functions take a PlayerView (or a Game) as `game`; they only read public
information.
"""

import math
from collections import Counter

from board import CARD_CELLS, CELL_CARD, LINE_CORNERS, LINES, LINES_THROUGH, TWO_EYED_JACKS
from game import EMPTY

# Value of an open line by how many of its 5 spaces count for its owner (0-4).
# "default" is the pilot's scale; the others exist for sensitivity analysis.
VALUE_SCALES = {
    "linear": (0.0, 1.0, 2.0, 3.0, 4.0),
    "flat": (0.0, 1.0, 2.0, 4.0, 8.0),
    "default": (0.0, 1.0, 4.0, 16.0, 128.0),
    "steep": (0.0, 1.0, 10.0, 100.0, 1000.0),
}
LINE_VALUE = VALUE_SCALES["default"]
COMPLETE = 1e4     # completing a sequence that doesn't win yet
WIN = 1e8          # completing the sequence that wins the game
STOP_WIN = 1e6     # blocking or breaking an opponent's four that would win them the game
EAGER_BONUS = 1e3  # 'eager' Jack policy: play a Jack unless something urgent is on
WILD_ONLY = 0.25   # card counting: weight of a space only a two-eyed Jack can still fill
THREAT_FLOOR = 0.05  # card counting: least urgency of a four that can still be filled

# How many lines pass through each space, scaled so the four central spaces
# (20 lines each) score 1 and the spaces next to the corners about 0.2.
CENTRALITY = tuple(len(LINES_THROUGH[c]) / 20.0 for c in range(100))


# ---- the basic scores (the pilot bots use only these) -----------------------------

def placement_value(game, p, cell, values=LINE_VALUE):
    """Score p putting a chip on the empty space `cell`.

    Returns (gain, block, completes, blocks_four).
    """
    o = 1 - p
    real_p, real_o = game.real[p], game.real[o]
    live_p, live_o = game.live[p], game.live[o]
    p_wins_next = len(game.sequences[p]) + 1 >= game.sequences_to_win
    o_wins_next = len(game.sequences[o]) + 1 >= game.sequences_to_win
    gain = block = 0.0
    completes = blocks_four = False
    for line in LINES_THROUGH[cell]:
        corners = LINE_CORNERS[line]
        if real_o[line] == 0 and live_p[line]:      # my open line gets one chip closer
            k = real_p[line] + corners
            if k == 4:
                gain += WIN if p_wins_next else COMPLETE
                completes = True
            else:
                gain += values[k + 1] - values[k]
        if real_p[line] == 0 and live_o[line]:      # their open line is now blocked
            k = real_o[line] + corners
            if k == 4:
                block += STOP_WIN if o_wins_next else values[4]
                blocks_four = True
            else:
                block += values[k]
    return gain, block, completes, blocks_four


def removal_value(game, p, cell, values=LINE_VALUE):
    """Score p using a one-eyed Jack on the opponent chip at `cell`.

    Returns (gain, block, breaks_four).
    """
    o = 1 - p
    real_p, real_o = game.real[p], game.real[o]
    live_p, live_o = game.live[p], game.live[o]
    o_wins_next = len(game.sequences[o]) + 1 >= game.sequences_to_win
    gain = block = 0.0
    breaks_four = False
    for line in LINES_THROUGH[cell]:
        corners = LINE_CORNERS[line]
        if real_p[line] == 0 and live_o[line]:      # their open line loses a chip
            k = real_o[line] + corners               # includes the chip being removed
            if k == 4:
                block += (STOP_WIN if o_wins_next else values[4]) - values[3]
                breaks_four = True
            else:
                block += values[k] - values[k - 1]
        if real_o[line] == 1 and live_p[line]:      # that chip was all that blocked my line
            gain += values[real_p[line] + corners]
    return gain, block, breaks_four


def critical_cells(game, p):
    """Spaces where a wild Jack would complete a four (p's or the opponent's), and
    opponent chips a one-eyed Jack could take out of an opponent four."""
    o = 1 - p
    board = game.board
    wild, removable = set(), set()
    for owner in (p, o):
        real_owner, real_other, live = game.real[owner], game.real[1 - owner], game.live[owner]
        for i, line in enumerate(LINES):
            if live[i] and real_other[i] == 0 and real_owner[i] + LINE_CORNERS[i] == 4:
                for c in line:
                    if board[c] == EMPTY:
                        wild.add(c)
                    elif owner == o and board[c] == o and not game.locked[c]:
                        removable.add(c)
    return wild, removable


# ---- card counting ('counter', 'bayes') ----------------------------------------------

def none_chance(total, good, drawn):
    """Chance that `drawn` cards taken at random from `total` include none of the `good` ones."""
    if drawn <= 0 or good <= 0:
        return 1.0
    if total - good < drawn:
        return 0.0
    return math.comb(total - good, drawn) / math.comb(total, drawn)


class CardInfo:
    """What player p can work out about the cards from public information alone."""

    def __init__(self, view, p):
        self.board = view.board
        self.hand = Counter(view.hand)
        self.unseen = view.unseen_counts()           # in the deck or the opponent's hand
        self.n_unseen = sum(self.unseen.values())
        self.opp_hand = view.opponent_hand_size
        self.wild_unseen = self.unseen["JD"] + self.unseen["JC"]
        self.wild_in_hand = self.hand["JD"] + self.hand["JC"]
        self.inferred = {}  # gap -> chance, from inferred_gap_chances() ('bayes' only)

    def opp_fill_chance(self, cell):
        """Chance the opponent holds, right now, a card that can go on `cell`:
        a copy of its card or a two-eyed Jack (hypergeometric over unseen cards)."""
        if cell in self.inferred:
            return self.inferred[cell]
        good = self.unseen[CELL_CARD[cell]] + self.wild_unseen
        return 1.0 - none_chance(self.n_unseen, good, self.opp_hand)

    def threat(self, gap):
        """Urgency of an opponent four with this gap: the chance they fill it next
        turn, but at least THREAT_FLOOR while any card could still fill it."""
        chance = self.opp_fill_chance(gap)
        if self.opp_access(gap) > 0.0:
            chance = max(chance, THREAT_FLOOR)
        return chance

    def my_access(self, cell):
        """1 if p holds the space's card or a copy is still unseen, WILD_ONLY if only
        a two-eyed Jack can fill it, 0 if nothing can (until a reshuffle)."""
        card = CELL_CARD[cell]
        if self.hand[card] or self.unseen[card]:
            return 1.0
        return WILD_ONLY if (self.wild_in_hand or self.wild_unseen) else 0.0

    def opp_access(self, cell):
        """The same from the opponent's side: p's own cards are out of their reach."""
        if self.unseen[CELL_CARD[cell]]:
            return 1.0
        return WILD_ONLY if self.wild_unseen else 0.0

    def line_reach(self, line, skip, mine):
        """Product of access over the line's empty spaces, leaving out `skip`."""
        access = self.my_access if mine else self.opp_access
        reach = 1.0
        for c in LINES[line]:
            if c != skip and self.board[c] == EMPTY:
                reach *= access(c)
                if reach == 0.0:
                    break
        return reach


def counted_placement_value(game, p, cell, values, info):
    """placement_value, adjusted by card counting.

    A line counts for less when some of its empty spaces can now only be filled by a
    two-eyed Jack, and for nothing when no card can fill them. An opponent four is
    weighted by how likely they are to fill its gap on their next turn.
    """
    o = 1 - p
    real_p, real_o = game.real[p], game.real[o]
    live_p, live_o = game.live[p], game.live[o]
    p_wins_next = len(game.sequences[p]) + 1 >= game.sequences_to_win
    o_wins_next = len(game.sequences[o]) + 1 >= game.sequences_to_win
    gain = block = 0.0
    completes = blocks_four = False
    for line in LINES_THROUGH[cell]:
        corners = LINE_CORNERS[line]
        if real_o[line] == 0 and live_p[line]:
            k = real_p[line] + corners
            if k == 4:
                gain += WIN if p_wins_next else COMPLETE
                completes = True
            else:
                gain += (values[k + 1] - values[k]) * info.line_reach(line, cell, True)
        if real_p[line] == 0 and live_o[line]:
            k = real_o[line] + corners
            if k == 4:                               # `cell` is the gap of their four
                block += (STOP_WIN if o_wins_next else values[4]) * info.threat(cell)
                blocks_four = True
            else:
                block += values[k] * info.line_reach(line, None, False)
    return gain, block, completes, blocks_four


def counted_removal_value(game, p, cell, values, info):
    """removal_value, adjusted by card counting in the same way."""
    o = 1 - p
    board = game.board
    real_p, real_o = game.real[p], game.real[o]
    live_p, live_o = game.live[p], game.live[o]
    o_wins_next = len(game.sequences[o]) + 1 >= game.sequences_to_win
    gain = block = 0.0
    breaks_four = False
    for line in LINES_THROUGH[cell]:
        corners = LINE_CORNERS[line]
        if real_p[line] == 0 and live_o[line]:
            k = real_o[line] + corners
            if k == 4:
                gap = next(c for c in LINES[line] if board[c] == EMPTY)
                block += (STOP_WIN if o_wins_next else values[4]) * info.threat(gap) - values[3]
                breaks_four = True
            else:
                block += (values[k] - values[k - 1]) * info.line_reach(line, None, False)
        if real_o[line] == 1 and live_p[line]:
            reach = info.line_reach(line, None, True) * info.my_access(cell)
            gain += values[real_p[line] + corners] * reach
    return gain, block, breaks_four


def inferred_gap_chances(view, p, info):
    """'bayes': learn from the opponent's last turn which cards it does not hold.

    If the opponent had an open four before its last move and did not complete it,
    it held no copy of the gap's card and no two-eyed Jack (any non-random bot takes
    a sequence when it can). Since then it has drawn one card, so the chance it can
    fill that gap now is (fillers still unseen) / (cards it could have drawn).
    Returns {gap: chance}. Assumes the opponent is not the random bot.
    """
    history = view.history
    if not history or history[-1][0] == p:
        return {}
    o = 1 - p
    move = history[-1][1]
    cell = None if move is None else move.cell
    seqs = view.sequences[o]
    if cell is not None and seqs and cell in seqs[-1]:
        return {}  # it completed a different sequence instead, so nothing is learned
    drawable = max(1, info.n_unseen - info.opp_hand + 1)
    board = view.board
    chances = {}
    for i, line in enumerate(LINES):
        if cell in line or not view.open_four(o, i):
            continue  # the four didn't exist before its move, or there is none
        for c in line:
            if board[c] == EMPTY:
                fillers = info.unseen[CELL_CARD[c]] + info.wild_unseen
                chances[c] = min(1.0, fillers / drawable)
    return chances


# ---- other features ------------------------------------------------------------------

def fork_gaps(game, p, cell, existing):
    """'forker': the gaps of all of p's open fours after p puts a chip on `cell`.

    `existing` is the set of p's gaps before the move. Returns an empty set when the
    move creates no new four, so only moves that add a threat can earn a fork bonus.
    """
    o = 1 - p
    real_p, real_o, live_p = game.real[p], game.real[o], game.live[p]
    board = game.board
    new = set()
    for line in LINES_THROUGH[cell]:
        if real_o[line] == 0 and live_p[line] and real_p[line] + LINE_CORNERS[line] == 3:
            new.update(c for c in LINES[line] if c != cell and board[c] == EMPTY)
    if not new:
        return new
    gaps = existing | new
    gaps.discard(cell)
    return gaps


def hand_bonus(game, p, move, values, hand):
    """'planner': manage the hand.

    + values[2] for playing a card whose other space is already taken (use it before
    it dies). - half the value of the strongest opponent line through the card's
    other space, when that line has 3+ and this is our only copy (we may need the
    card to block there later).
    """
    if move.remove or move.card in TWO_EYED_JACKS:
        return 0.0
    a, b = CARD_CELLS[move.card]
    other = b if move.cell == a else a
    board = game.board
    if board[other] != EMPTY:
        return values[2]
    if hand.count(move.card) > 1:
        return 0.0
    o = 1 - p
    real_p, real_o, live_o = game.real[p], game.real[o], game.live[o]
    worst = 0
    for line in LINES_THROUGH[other]:
        if real_p[line] == 0 and live_o[line]:
            worst = max(worst, real_o[line] + LINE_CORNERS[line])
    return -0.5 * values[min(worst, 4)] if worst >= 3 else 0.0


def progress(game, q):
    """How close q is to winning: 5 per completed sequence plus q's best open line (0-4)."""
    real_q, real_o, live_q = game.real[q], game.real[1 - q], game.live[q]
    best = 0
    for line in range(len(LINES)):
        if live_q[line] and real_o[line] == 0:
            k = real_q[line] + LINE_CORNERS[line]
            if k > best:
                best = k
    return 5 * len(game.sequences[q]) + min(best, 4)


ADAPT_WEIGHTS = {"behind": (0.5, 1.5), "even": (1.0, 1.0), "ahead": (1.5, 0.5)}


def adaptive_weights(game, p):
    """'adaptive': (attack, defend) by who is closer to winning."""
    lead = progress(game, p) - progress(game, 1 - p)
    if lead <= -1:
        return ADAPT_WEIGHTS["behind"]
    if lead >= 1:
        return ADAPT_WEIGHTS["ahead"]
    return ADAPT_WEIGHTS["even"]


def phase_weights(game):
    """'phase': build early, defend late. Weights slide from (1.5, 0.5) on an empty
    board to (0.5, 1.5) once 48 chips are down."""
    chips = sum(1 for v in game.board if v == 0 or v == 1)
    f = min(1.0, chips / 48.0)
    return 1.5 - f, 0.5 + f


def opponent_response(view, p, move):
    """'reader': was the opponent's `move` an answer to a threat of p's?

    Returns (opportunity, responded). An opportunity is a turn that started with p
    holding an open line with 3+ spaces counted; a response is a move that put a
    chip on such a line or took a chip off it."""
    o = 1 - p
    real_p, real_o, live_p = view.real[p], view.real[o], view.live[p]
    through = set(LINES_THROUGH[move.cell])
    opportunity = False
    for line in range(len(LINES)):
        if not live_p[line]:
            continue
        hit = line in through
        before_o = real_o[line] - (1 if hit and not move.remove else 0)
        before_p = real_p[line] + (1 if hit and move.remove else 0)
        if before_o == 0 and before_p + LINE_CORNERS[line] >= 3:
            opportunity = True
            if hit:
                return True, True
    return opportunity, False


def observe_opponent(view, p):
    """'reader': update p's notes with the opponent's newest move and return its
    estimated defensiveness, (responses + 1) / (opportunities + 2)."""
    notes = view.notes
    history = view.history
    seen = notes.get("reader_seen", 0)
    chances, responses = notes.get("reader_counts", (0, 0))
    for entry in reversed(history[seen:]):
        if entry[0] != p:
            if entry[1] is not None:
                opportunity, responded = opponent_response(view, p, entry[1])
                chances += opportunity
                responses += responded
            break
    notes["reader_seen"] = len(history)
    notes["reader_counts"] = (chances, responses)
    return (responses + 1) / (chances + 2)


def logit_choice(scored, lam, rng):
    """'logit': pick a move with probability proportional to exp(lam * score)."""
    top = max(score for score, _, _ in scored)
    weights = [math.exp(lam * (score - top)) for score, _, _ in scored]
    return rng.choices([move for _, _, move in scored], weights=weights, k=1)[0]


def best_move(scored, rng):
    """Highest score wins; on a tie, prefer moves that keep the Jack; then pick at random."""
    top = max(score for score, _, _ in scored)
    tied = [(jack, move) for score, jack, move in scored if score >= top - 1e-9 * max(1.0, abs(top))]
    if not all(jack for jack, _ in tied):
        tied = [(jack, move) for jack, move in tied if not jack]
    return tied[0][1] if len(tied) == 1 else rng.choice(tied)[1]
