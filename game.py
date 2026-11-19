"""Rules engine for two-player Sequence.

Rules implemented (official rules for 2 players unless marked otherwise):
- Two standard decks (104 cards). Each player is dealt 7 cards.
- On your turn, play a card, put a chip on one of its two spaces, then draw.
- Two-eyed Jacks (JD, JC) are wild: put a chip on any open space.
- One-eyed Jacks (JS, JH) remove one opponent chip that isn't in a completed sequence.
- The four corners are free spaces that count as a chip for both players.
- A sequence is 5 in a row: across, down or diagonal. Your second sequence may
  share one space with your first. Chips in a completed sequence can't be removed.
- The first player to complete 2 sequences wins.
- Dead cards (both spaces already taken) may be traded in, one per turn, at the
  start of your turn. Simplification: players always trade one in when they can.
- House rules: when the draw pile runs out, the discards are reshuffled into a new
  draw pile; a player with no legal move passes; play_game() calls the game a draw
  after `max_turns` plies.

Bots never see the Game itself. Each bot gets a PlayerView, which shows the board,
its own hand and everything played face up, but not the opponent's hand or the deck.
"""

import random
from collections import Counter
from typing import NamedTuple

from board import (CARD_CELLS, CELL_CARD, IS_CORNER, JACKS, LINE_CORNERS, LINES,
                   LINES_THROUGH, ONE_EYED_JACKS, SIZE, TWO_EYED_JACKS, full_deck)

EMPTY = -1
FREE_SPACE = 2  # board value of the four corners; the players are 0 and 1
N_CELLS = SIZE * SIZE
FULL_DECK_COUNTS = Counter(full_deck())  # every card -> 2

# Per-seat counters, copied by Game.clone() and written to the tournament CSV.
_COUNTERS = ("two_eyed_used", "one_eyed_used", "jack_finishes", "jack_blocks",
             "jack_breaks", "dead_swaps", "passes")


class Move(NamedTuple):
    card: str
    cell: int
    remove: bool = False  # True when a one-eyed Jack takes an opponent chip off


class Game:
    """The full state of one two-player game, hidden information included.

    Useful attributes:
      board[cell]     EMPTY, 0 or 1 (a player's chip), or FREE_SPACE (a corner)
      locked[cell]    True if the chip is part of a completed sequence
      real[p][line]   how many of p's chips are on that line (corners not included)
      live[p][line]   False once the line can no longer become a new sequence for p,
                      because it shares 2+ spaces with one of p's sequences
      sequences[p]    p's completed sequences, each a tuple of 5 cells
      hands[p]        p's cards (hidden from the opponent)
      deck            the draw pile, last card drawn first (hidden from both)

    Jack statistics, per seat: jack_finishes (two-eyed Jacks that completed a
    sequence), jack_blocks (two-eyed Jacks placed in the gap of an opponent's open
    four), jack_breaks (one-eyed Jacks that took a chip out of an opponent's open four).
    """

    def __init__(self, seed, hand_size=7, sequences_to_win=2):
        # This RNG only shuffles cards, so a given seed always deals the same cards
        # to the same seats, whichever bots are playing.
        self.rng = random.Random(seed)
        self.deck = full_deck()
        self.rng.shuffle(self.deck)
        self.discards = []
        self.sequences_to_win = sequences_to_win
        self.board = [FREE_SPACE if IS_CORNER[c] else EMPTY for c in range(N_CELLS)]
        self.locked = [False] * N_CELLS
        self.real = ([0] * len(LINES), [0] * len(LINES))
        self.live = ([True] * len(LINES), [True] * len(LINES))
        self.sequences = ([], [])
        self.hands = ([], [])
        for p in (0, 1):
            for _ in range(hand_size):
                self.hands[p].append(self.deck.pop())
        self.to_move = 0
        self.turn = 0          # plies played so far
        self.winner = None     # 0 or 1 once someone wins; stays None in a draw
        self.history = []      # (player, Move or None for a pass, dead card traded or None)
        for name in _COUNTERS:
            setattr(self, name, [0, 0])
        self.reshuffles = 0
        self.notes = ({}, {})  # per-seat scratch space for bots that remember things
        self.views = (PlayerView(self, 0), PlayerView(self, 1))

    # ---- reading the position -------------------------------------------------

    def count(self, p, line):
        """Spaces of `line` that count for p: p's chips plus any corner."""
        return self.real[p][line] + LINE_CORNERS[line]

    def open_four(self, p, line):
        """True if `line` is one chip away from a new sequence for p: 4 of its 5
        spaces count for p, the opponent has no chip on it, and it is still live."""
        return (self.live[p][line] and self.real[1 - p][line] == 0
                and self.real[p][line] + LINE_CORNERS[line] == 4)

    def threat_gaps(self, p):
        """The empty spaces where one more chip would complete a new sequence for p."""
        board = self.board
        gaps = set()
        for i, line in enumerate(LINES):
            if self.open_four(p, i):
                gaps.update(c for c in line if board[c] == EMPTY)
        return gaps

    def is_dead(self, card):
        """True for a non-Jack card whose two spaces are both taken."""
        if card in JACKS:
            return False
        a, b = CARD_CELLS[card]
        return self.board[a] != EMPTY and self.board[b] != EMPTY

    def unseen_counts(self, p):
        """Copies of each card that p has not seen: in the deck or the opponent's hand.

        Computed only from public information (all cards, minus p's hand, minus the
        face-up discards), so bots may use it."""
        return FULL_DECK_COUNTS - Counter(self.hands[p]) - Counter(self.discards)

    def legal_moves(self, p):
        """Every legal move for player p.

        Duplicate cards, and the two Jacks of each kind, produce their moves only
        once, since they allow exactly the same plays.
        """
        board = self.board
        moves = []
        wild_done = remove_done = False
        for card in sorted(set(self.hands[p])):  # sorted: sets of strings don't iterate in a fixed order
            if card in TWO_EYED_JACKS:
                if not wild_done:
                    moves.extend(Move(card, c) for c in range(N_CELLS) if board[c] == EMPTY)
                    wild_done = True
            elif card in ONE_EYED_JACKS:
                if not remove_done:
                    opp, locked = 1 - p, self.locked
                    moves.extend(Move(card, c, True) for c in range(N_CELLS)
                                 if board[c] == opp and not locked[c])
                    remove_done = True
            else:
                moves.extend(Move(card, c) for c in CARD_CELLS[card] if board[c] == EMPTY)
        return moves

    # ---- playing --------------------------------------------------------------

    def play_turn(self, bot, rng):
        """Play one full turn for the player to move. Returns the Move, or None for a pass."""
        p = self.to_move
        traded = self._trade_dead_card(p)
        moves = self.legal_moves(p)
        move = None
        if moves:
            move = bot.choose(self.views[p], p, moves, rng)
            if move not in moves:
                raise ValueError(f"{getattr(bot, 'name', bot)!s} chose an illegal move: {move}")
        self.play_move(p, move, traded)
        return move

    def play_move(self, p, move, traded=None):
        """Finish p's turn with `move` (None means a pass), then hand the turn over."""
        if move is None:
            self.passes[p] += 1
        else:
            self.apply(p, move)
        self.history.append((p, move, traded))
        self.turn += 1
        if self.winner is None:
            self.to_move = 1 - p

    def apply(self, p, move):
        """Play `move` for p: use the card, change the board, draw a replacement."""
        o = 1 - p
        self.hands[p].remove(move.card)
        self.discards.append(move.card)
        if move.remove:
            if any(self.open_four(o, line) for line in LINES_THROUGH[move.cell]):
                self.jack_breaks[p] += 1
            self.remove_chip(move.cell)
            self.one_eyed_used[p] += 1
        elif move.card in TWO_EYED_JACKS:
            self.two_eyed_used[p] += 1
            blocks = any(self.open_four(o, line) for line in LINES_THROUGH[move.cell])
            before = len(self.sequences[p])
            self.place_chip(p, move.cell)
            if len(self.sequences[p]) > before:
                self.jack_finishes[p] += 1
            elif blocks:
                self.jack_blocks[p] += 1
        else:
            self.place_chip(p, move.cell)
        self._draw(p)

    def place_chip(self, p, cell):
        """Put p's chip on an empty space and claim any sequence it completes.

        Also handy for setting up positions in tests or experiments.
        """
        if self.board[cell] != EMPTY:
            raise ValueError(f"cell {cell} is not empty")
        self.board[cell] = p
        real = self.real[p]
        for line in LINES_THROUGH[cell]:
            real[line] += 1
        self._claim_sequences(p, cell)

    def remove_chip(self, cell):
        """Take a chip off the board (what a one-eyed Jack does)."""
        owner = self.board[cell]
        if owner not in (0, 1) or self.locked[cell]:
            raise ValueError(f"cell {cell} has no removable chip")
        self.board[cell] = EMPTY
        real = self.real[owner]
        for line in LINES_THROUGH[cell]:
            real[line] -= 1

    def _claim_sequences(self, p, cell):
        # Only lines through the new chip can have just been completed.
        real, live = self.real[p], self.live[p]
        for line in LINES_THROUGH[cell]:
            # live[line] is re-read on each pass, so after one line is claimed, any
            # line sharing 2+ spaces with it (e.g. the rest of a row of 6) is skipped.
            if live[line] and real[line] + LINE_CORNERS[line] == 5:
                cells = LINES[line]
                self.sequences[p].append(cells)
                for c in cells:
                    self.locked[c] = True
                self._retire_overlapping_lines(p, cells)
        if len(self.sequences[p]) >= self.sequences_to_win:
            self.winner = p

    def _retire_overlapping_lines(self, p, sequence):
        """A new sequence may share only one space with an earlier one."""
        taken = set(sequence)
        live = self.live[p]
        for i, line in enumerate(LINES):
            if live[i] and sum(c in taken for c in line) >= 2:
                live[i] = False

    def _trade_dead_card(self, p):
        hand = self.hands[p]
        for i, card in enumerate(hand):
            if self.is_dead(card):
                self.discards.append(hand.pop(i))
                self._draw(p)
                self.dead_swaps[p] += 1
                return card
        return None

    def _draw(self, p):
        if not self.deck:
            if not self.discards:
                return
            self.deck, self.discards = self.discards, []
            self.rng.shuffle(self.deck)
            self.reshuffles += 1
        self.hands[p].append(self.deck.pop())

    # ---- copies, for lookahead ------------------------------------------------

    def clone(self):
        """An independent copy of the whole game. Bots' notes are not copied."""
        g = Game.__new__(Game)
        g.rng = random.Random()
        g.rng.setstate(self.rng.getstate())
        g.deck = list(self.deck)
        g.discards = list(self.discards)
        g.sequences_to_win = self.sequences_to_win
        g.board = list(self.board)
        g.locked = list(self.locked)
        g.real = (list(self.real[0]), list(self.real[1]))
        g.live = (list(self.live[0]), list(self.live[1]))
        g.sequences = (list(self.sequences[0]), list(self.sequences[1]))
        g.hands = (list(self.hands[0]), list(self.hands[1]))
        g.to_move = self.to_move
        g.turn = self.turn
        g.winner = self.winner
        g.history = list(self.history)
        for name in _COUNTERS:
            setattr(g, name, list(getattr(self, name)))
        g.reshuffles = self.reshuffles
        g.notes = ({}, {})
        g.views = (PlayerView(g, 0), PlayerView(g, 1))
        return g

    def determinize(self, p, rng):
        """A copy of the game in which everything p cannot see is dealt again at random.

        The opponent's hand and the deck are refilled from the cards p has not seen
        (all cards, minus p's hand, minus the face-up discards), so the copy agrees
        with everything p knows. This is how the sampler bot imagines the hidden cards.
        """
        g = self.clone()
        o = 1 - p
        pool = sorted(self.unseen_counts(p).elements())
        rng.shuffle(pool)
        n = len(g.hands[o])
        g.hands[o][:] = pool[:n]
        g.deck = pool[n:]
        g.rng = random.Random(rng.getrandbits(64))  # future reshuffles in the copy
        return g

    # ---- debugging ------------------------------------------------------------

    def render(self, marks="XO"):
        """The board as text: card labels on open spaces, X/O for chips,
        [X]/[O] for chips locked in a sequence, * for corners."""
        rows = []
        for r in range(SIZE):
            out = []
            for c in range(SIZE):
                cell = r * SIZE + c
                value = self.board[cell]
                if value == FREE_SPACE:
                    out.append(" * ")
                elif value == EMPTY:
                    out.append(f"{CELL_CARD[cell]} ")
                elif self.locked[cell]:
                    out.append(f"[{marks[value]}]")
                else:
                    out.append(f" {marks[value]} ")
            rows.append(" ".join(out))
        return "\n".join(rows)

    def check_consistency(self):
        """Recompute the line counts from scratch and compare. Raises AssertionError on a bug."""
        for p in (0, 1):
            for i, line in enumerate(LINES):
                actual = sum(self.board[c] == p for c in line)
                assert self.real[p][i] == actual, f"line {i} count for player {p}"
                if self.live[p][i]:
                    assert self.count(p, i) < 5, f"live full line {i} for player {p}"
            for seq in self.sequences[p]:
                assert all(self.board[c] in (p, FREE_SPACE) and self.locked[c] for c in seq)
            seqs = self.sequences[p]
            for a in range(len(seqs)):
                for b in range(a + 1, len(seqs)):
                    assert len(set(seqs[a]) & set(seqs[b])) <= 1, "sequences overlap"
        cards = len(self.deck) + len(self.discards) + len(self.hands[0]) + len(self.hands[1])
        assert cards == 104, f"{cards} cards in play"


class PlayerView:
    """What one player may see: the board, their own hand, and everything played face up.

    Bots receive one of these instead of the Game, so no strategy can read the
    opponent's hand or the order of the deck, even by accident. Treat every list
    here as read-only.
    """

    __slots__ = ("_game", "player")

    def __init__(self, game, player):
        self._game = game
        self.player = player

    board = property(lambda self: self._game.board)
    locked = property(lambda self: self._game.locked)
    real = property(lambda self: self._game.real)
    live = property(lambda self: self._game.live)
    sequences = property(lambda self: self._game.sequences)
    sequences_to_win = property(lambda self: self._game.sequences_to_win)
    turn = property(lambda self: self._game.turn)
    to_move = property(lambda self: self._game.to_move)
    winner = property(lambda self: self._game.winner)
    history = property(lambda self: self._game.history)    # public: every move and traded card
    discards = property(lambda self: self._game.discards)  # public: the face-up pile
    two_eyed_used = property(lambda self: self._game.two_eyed_used)
    one_eyed_used = property(lambda self: self._game.one_eyed_used)

    @property
    def hand(self):
        """This player's own cards."""
        return tuple(self._game.hands[self.player])

    @property
    def opponent_hand_size(self):
        return len(self._game.hands[1 - self.player])

    @property
    def deck_size(self):
        return len(self._game.deck)

    @property
    def notes(self):
        """A scratch dict for this seat's bot that lasts for the whole game."""
        return self._game.notes[self.player]

    def count(self, p, line):
        return self._game.count(p, line)

    def open_four(self, p, line):
        return self._game.open_four(p, line)

    def threat_gaps(self, p):
        return self._game.threat_gaps(p)

    def is_dead(self, card):
        return self._game.is_dead(card)

    def unseen_counts(self):
        return self._game.unseen_counts(self.player)

    def determinize(self, rng):
        return self._game.determinize(self.player, rng)

    def render(self, marks="XO"):
        return self._game.render(marks)


def seat_rngs(seed):
    """One random stream per seat for the bots' tie-breaking, separate from the deck."""
    return random.Random(seed * 1_000_003 + 1), random.Random(seed * 1_000_003 + 2)


def play_game(bot0, bot1, seed, max_turns=500, observer=None, **game_options):
    """Play one game to the end and return the finished Game.

    `observer(game, player, move)` is called after every turn if given.
    """
    game = Game(seed, **game_options)
    bots = (bot0, bot1)
    rngs = seat_rngs(seed)
    while game.winner is None and game.turn < max_turns:
        p = game.to_move
        move = game.play_turn(bots[p], rngs[p])
        if observer is not None:
            observer(game, p, move)
    return game
