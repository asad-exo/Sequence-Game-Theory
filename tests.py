"""Tests for the board, the rules engine, the strategies and the scripts.

    python -m unittest -v tests

Cells are row * 10 + col, so cell 45 is row 4, column 5.
"""

import csv
import os
import random
import unittest
from collections import Counter

from board import CARD_CELLS, CELL_CARD, CORNERS, LINES, LINES_THROUGH, SIZE, full_deck
from bots import DEFAULT_BOTS, ROSTERS, make_bot
from game import EMPTY, Game, Move, play_game, seat_rngs
from scoring import (VALUE_SCALES, CardInfo, adaptive_weights, counted_placement_value,
                     inferred_gap_chances, observe_opponent, phase_weights, placement_value)
from tournament import FIELDS, run_game, schedule

HERE = os.path.dirname(os.path.abspath(__file__))


def empty_game(seed=0):
    """A fresh game with both hands emptied, for setting up positions by hand."""
    game = Game(seed)
    game.hands[0].clear()
    game.hands[1].clear()
    return game


def place(game, p, cells):
    for cell in cells:
        game.place_chip(p, cell)


def played(seed, turns, specs=("mixed", "mixed")):
    """A game after `turns` plies of normal play."""
    game = Game(seed)
    bots = (make_bot(specs[0]), make_bot(specs[1]))
    rngs = seat_rngs(seed)
    for _ in range(turns):
        if game.winner is not None:
            break
        game.play_turn(bots[game.to_move], rngs[game.to_move])
    return game


class BoardTests(unittest.TestCase):
    def test_every_card_has_two_spaces(self):
        self.assertEqual(len(CARD_CELLS), 48)
        self.assertTrue(all(len(cells) == 2 for cells in CARD_CELLS.values()))
        self.assertEqual(CORNERS, (0, 9, 90, 99))

    def test_192_straight_lines_of_five(self):
        self.assertEqual(len(LINES), 192)
        self.assertEqual(len(set(LINES)), 192)
        for line in LINES:
            rows = [c // SIZE for c in line]
            cols = [c % SIZE for c in line]
            dr = {rows[i + 1] - rows[i] for i in range(4)}
            dc = {cols[i + 1] - cols[i] for i in range(4)}
            self.assertEqual(len(dr), 1)
            self.assertEqual(len(dc), 1)
            self.assertIn((dr.pop(), dc.pop()), {(0, 1), (1, 0), (1, 1), (1, -1)})
        for cell in range(SIZE * SIZE):
            self.assertEqual(set(LINES_THROUGH[cell]), {i for i, l in enumerate(LINES) if cell in l})

    def test_deck(self):
        deck = full_deck()
        self.assertEqual(len(deck), 104)
        self.assertEqual(sum(card[0] == "J" for card in deck), 8)


class SequenceTests(unittest.TestCase):
    def test_horizontal_sequence(self):
        game = empty_game()
        place(game, 0, [41, 42, 43, 44])
        self.assertEqual(game.sequences[0], [])
        game.place_chip(0, 45)
        self.assertEqual(game.sequences[0], [(41, 42, 43, 44, 45)])
        self.assertTrue(all(game.locked[c] for c in (41, 42, 43, 44, 45)))
        self.assertIsNone(game.winner)  # one sequence isn't enough with 2 players

    def test_vertical_and_diagonal_sequences(self):
        # (Diagonals chosen away from the corners, which would complete a line earlier.)
        for cells in ([5, 15, 25, 35, 45], [12, 23, 34, 45, 56], [17, 26, 35, 44, 53]):
            game = empty_game()
            place(game, 1, cells)
            self.assertEqual(game.sequences[1], [tuple(cells)])

    def test_corner_counts_for_both_players(self):
        game = empty_game()
        place(game, 0, [1, 2, 3, 4])
        self.assertEqual(game.sequences[0], [(0, 1, 2, 3, 4)])
        place(game, 1, [10, 20, 30, 40])
        self.assertEqual(game.sequences[1], [(0, 10, 20, 30, 40)])

    def test_opponent_chip_blocks(self):
        game = empty_game()
        place(game, 0, [41, 42, 44, 45])
        game.place_chip(1, 43)
        self.assertEqual(game.sequences[0], [])

    def test_second_sequence_may_share_one_space(self):
        game = empty_game()
        place(game, 0, [40, 41, 42, 43, 44])
        place(game, 0, [4, 14, 24, 34])
        self.assertEqual(len(game.sequences[0]), 2)
        self.assertEqual(game.winner, 0)

    def test_row_of_six_is_one_sequence(self):
        game = empty_game()
        place(game, 0, [60, 61, 62, 63, 64, 65])
        self.assertEqual(game.sequences[0], [(60, 61, 62, 63, 64)])

    def test_row_of_nine_is_two_sequences(self):
        game = empty_game()
        place(game, 0, range(50, 58))
        self.assertEqual(len(game.sequences[0]), 1)
        self.assertIsNone(game.winner)
        game.place_chip(0, 58)
        self.assertEqual(game.sequences[0], [(50, 51, 52, 53, 54), (54, 55, 56, 57, 58)])
        self.assertEqual(game.winner, 0)

    def test_one_chip_can_complete_two_sequences(self):
        game = empty_game()
        place(game, 0, [40, 41, 42, 43, 4, 14, 24, 34])
        self.assertEqual(game.sequences[0], [])
        game.place_chip(0, 44)
        self.assertEqual(len(game.sequences[0]), 2)
        self.assertEqual(game.winner, 0)

    def test_one_sequence_to_win_variant(self):
        game = Game(0, sequences_to_win=1)
        game.hands[0].clear()
        place(game, 0, [41, 42, 43, 44, 45])
        self.assertEqual(game.winner, 0)


class JackAndCardTests(unittest.TestCase):
    def test_one_eyed_jack_cannot_touch_a_sequence(self):
        game = empty_game()
        place(game, 1, [71, 72, 73, 74, 75, 82])
        game.hands[0].append("JS")
        removable = {m.cell for m in game.legal_moves(0)}
        self.assertEqual(removable, {82})
        with self.assertRaises(ValueError):
            game.remove_chip(73)

    def test_one_eyed_jack_needs_a_target(self):
        game = empty_game()
        game.place_chip(0, 44)           # own chips can't be removed
        game.hands[0].append("JH")
        self.assertEqual(game.legal_moves(0), [])

    def test_two_eyed_jack_goes_on_any_open_space(self):
        game = empty_game()
        place(game, 0, [12, 13])
        game.place_chip(1, 77)
        game.hands[0].append("JD")
        cells = {m.cell for m in game.legal_moves(0)}
        self.assertEqual(len(cells), 96 - 3)
        self.assertFalse(cells & set(CORNERS))
        self.assertFalse(cells & {12, 13, 77})

    def test_normal_card_needs_an_open_space(self):
        game = empty_game()
        a, b = CARD_CELLS["7H"]
        game.hands[0].append("7H")
        self.assertEqual({m.cell for m in game.legal_moves(0)}, {a, b})
        game.place_chip(1, a)
        self.assertEqual({m.cell for m in game.legal_moves(0)}, {b})
        game.place_chip(1, b)
        self.assertTrue(game.is_dead("7H"))
        self.assertEqual(game.legal_moves(0), [])

    def test_dead_card_is_traded_in(self):
        game = empty_game()
        for cell in CARD_CELLS["2S"]:
            game.place_chip(1, cell)
        game.hands[0].extend(["2S", "3S"])
        game.deck = ["4H", "5H"]
        game.play_turn(make_bot("mixed"), random.Random(0))
        player, move, traded = game.history[-1]
        self.assertEqual(traded, "2S")
        self.assertEqual(game.dead_swaps[0], 1)
        self.assertNotIn("2S", game.hands[0])
        self.assertIn(move.card, ("3S", "5H"))

    def test_draw_pile_is_reshuffled_when_empty(self):
        game = empty_game()
        game.hands[0].append("3S")
        game.deck = []
        game.discards = ["9C", "9D"]
        game.apply(0, Move("3S", CARD_CELLS["3S"][0]))
        self.assertEqual(game.reshuffles, 1)
        self.assertEqual(len(game.hands[0]), 1)


class JackStatTests(unittest.TestCase):
    def test_wild_jack_that_completes_a_sequence(self):
        game = empty_game()
        place(game, 0, [41, 42, 43, 44])
        game.hands[0].append("JD")
        game.apply(0, Move("JD", 45))
        self.assertEqual((game.jack_finishes[0], game.jack_blocks[0]), (1, 0))

    def test_wild_jack_that_blocks_a_four(self):
        game = empty_game()
        place(game, 1, [41, 42, 43, 44])
        game.hands[0].append("JC")
        game.apply(0, Move("JC", 45))
        self.assertEqual((game.jack_finishes[0], game.jack_blocks[0]), (0, 1))

    def test_one_eyed_jack_that_breaks_a_four(self):
        game = empty_game()
        place(game, 1, [41, 42, 43, 44])
        game.hands[0].append("JS")
        game.apply(0, Move("JS", 42, True))
        self.assertEqual(game.jack_breaks[0], 1)
        self.assertEqual(game.board[42], EMPTY)


class ViewTests(unittest.TestCase):
    def test_view_hides_hidden_information(self):
        game = Game(3)
        view = game.views[0]
        self.assertEqual(view.hand, tuple(game.hands[0]))
        self.assertEqual(view.opponent_hand_size, 7)
        self.assertEqual(view.deck_size, len(game.deck))
        for name in ("deck", "hands", "rng"):
            with self.assertRaises(AttributeError):
                getattr(view, name)

    def test_unseen_cards_are_exactly_the_hidden_ones(self):
        game = played(4, 30)
        for p in (0, 1):
            self.assertEqual(game.views[p].unseen_counts(),
                             Counter(game.deck) + Counter(game.hands[1 - p]))

    def test_clone_is_independent(self):
        game = Game(6)
        copy = game.clone()
        copy.play_move(0, copy.legal_moves(0)[0])
        self.assertEqual(game.turn, 0)
        self.assertEqual(copy.turn, 1)
        self.assertNotEqual(copy.board, game.board)
        game.check_consistency()
        copy.check_consistency()

    def test_determinize_keeps_what_the_player_knows(self):
        game = played(5, 12)
        world = game.determinize(0, random.Random(1))
        self.assertEqual(world.board, game.board)
        self.assertEqual(world.hands[0], game.hands[0])
        self.assertEqual(world.discards, game.discards)
        self.assertEqual(len(world.hands[1]), len(game.hands[1]))
        self.assertEqual(len(world.deck), len(game.deck))
        self.assertEqual(Counter(world.deck) + Counter(world.hands[1]),
                         Counter(game.deck) + Counter(game.hands[1]))
        world.check_consistency()
        other = game.determinize(0, random.Random(2))
        self.assertNotEqual((world.hands[1], world.deck), (other.hands[1], other.deck))


def score_of(spec, view, move):
    """A heuristic bot's score for one move."""
    (score, _, _), = make_bot(spec).score_moves(view, view.player, [move])
    return score


class BotTests(unittest.TestCase):
    def position_with_four(self, owner, hand):
        """`owner` holds row 4, columns 1-4. Column 5 (4H) is the open space."""
        game = empty_game()
        place(game, owner, [41, 42, 43, 44])
        game.hands[0].extend(hand)
        return game

    def choose(self, spec, game, seed=0):
        return make_bot(spec).choose(game.views[0], 0, game.legal_moves(0), random.Random(seed))

    def test_bots_complete_a_sequence(self):
        for spec in ROSTERS["full"]:
            if spec == "random":
                continue
            game = self.position_with_four(0, ["4H", "2S", "3S"])
            self.assertEqual(self.choose(spec, game), Move("4H", 45), spec)

    def test_defensive_bots_block_a_four(self):
        for spec in ("blocker", "mixed", "mixed_save", "counter", "bayes", "adaptive", "expert"):
            game = self.position_with_four(1, ["4H", "2S", "3S"])
            game.hands[1].extend(["2C", "3C", "4C", "5C", "6C", "7C", "8C"])
            self.assertEqual(self.choose(spec, game), Move("4H", 45), spec)

    def test_saver_keeps_a_wild_jack_when_nothing_is_urgent(self):
        for seed in range(20):
            game = empty_game()
            game.hands[0].extend(["JD", "2S", "3S"])
            self.assertNotEqual(self.choose("mixed_save", game, seed).card, "JD")

    def test_saver_uses_a_wild_jack_to_finish(self):
        game = self.position_with_four(0, ["JD", "2S", "3S"])
        move = self.choose("mixed_save", game)
        self.assertEqual(move.card, "JD")
        self.assertIn(move.cell, (40, 45))  # either end of the four finishes a sequence

    def test_saver_uses_a_one_eyed_jack_to_break_a_four(self):
        game = self.position_with_four(1, ["JS", "2S", "3S"])
        move = self.choose("mixed_save", game)
        self.assertEqual(move.card, "JS")
        self.assertIn(move.cell, (41, 42, 43, 44))

    def test_jack_timing_variants(self):
        game = empty_game()
        game.place_chip(1, 77)
        game.hands[0].extend(["JD", "JS", "2S"])
        self.assertIn(self.choose("eager", game).card, ("JD", "JS"))
        self.assertNotEqual(self.choose("save_wild", game).card, "JD")
        self.assertNotEqual(self.choose("save_remove", game).card, "JS")

    def test_center_bonus(self):
        game = empty_game()
        game.hands[0].append("5H")
        move = Move("5H", 44)  # a central space, centrality 1
        diff = score_of("center", game.views[0], move) - score_of("mixed_save", game.views[0], move)
        self.assertAlmostEqual(diff, 10.0)

    def test_fork_bonus(self):
        game = empty_game()
        place(game, 0, [41, 42, 43, 14, 24, 34])
        game.hands[0].append("5H")
        move = Move("5H", 44)  # makes fours along row 4 and column 4: gaps 40, 45, 4 and 54
        diff = score_of("forker", game.views[0], move) - score_of("mixed_save", game.views[0], move)
        self.assertAlmostEqual(diff, 3 * 128.0)

    def test_planner_bonus_and_penalty(self):
        game = empty_game()
        game.place_chip(1, 68)  # 5H's other space is taken: use the card or lose it
        game.hands[0].append("5H")
        move = Move("5H", 44)
        self.assertAlmostEqual(score_of("planner", game.views[0], move)
                               - score_of("mixed_save", game.views[0], move), 4.0)
        game = empty_game()
        place(game, 1, [65, 66, 67])  # the opponent builds toward 68, 5H's other space
        game.hands[0].append("5H")
        self.assertAlmostEqual(score_of("planner", game.views[0], move)
                               - score_of("mixed_save", game.views[0], move), -8.0)

    def test_counter_ignores_a_four_nobody_can_fill(self):
        game = empty_game()
        place(game, 1, [41, 42, 43, 44])  # gaps 40 (9C) and 45 (4H)
        game.hands[0].extend(["4H", "2S", "3S"])
        game.hands[1].extend(["2C", "3C", "4C", "5C", "6C", "7C", "8C"])
        view = game.views[0]
        values = VALUE_SCALES["default"]
        self.assertGreater(counted_placement_value(view, 0, 45, values, CardInfo(view, 0))[1], 1.0)
        game.discards = ["4H", "9C", "9C", "JD", "JD", "JC", "JC"]  # every other filler is gone
        self.assertEqual(counted_placement_value(view, 0, 45, values, CardInfo(view, 0))[1], 0.0)
        self.assertGreaterEqual(placement_value(view, 0, 45)[1], 128.0)

    def test_bayes_learns_from_a_skipped_completion(self):
        game = empty_game()
        place(game, 1, [41, 42, 43, 44, 77])
        game.hands[0].extend(["2S", "3S", "6S"])
        game.hands[1].extend(["2C", "3C", "4C", "5C", "6C", "7C", "8C"])
        game.history.append((1, Move("KD", 77), None))  # it played elsewhere, leaving its four
        view = game.views[0]
        info = CardInfo(view, 0)
        inferred = inferred_gap_chances(view, 0, info)
        self.assertEqual(set(inferred), {40, 45})
        self.assertLess(inferred[45], info.opp_fill_chance(45))
        game.history[-1] = (1, Move("5H", 44), None)  # the four was only just made: nothing learned
        self.assertEqual(inferred_gap_chances(view, 0, info), {})

    def test_adaptive_and_phase_weights(self):
        game = empty_game()
        self.assertEqual(adaptive_weights(game.views[0], 0), (1.0, 1.0))
        self.assertEqual(phase_weights(game.views[0]), (1.5, 0.5))
        place(game, 1, [21, 22, 23, 24, 25])  # the opponent completes a sequence
        self.assertEqual(adaptive_weights(game.views[0], 0), (0.5, 1.5))
        self.assertEqual(adaptive_weights(game.views[1], 1), (1.5, 0.5))
        game = empty_game()
        place(game, 0, [11, 13, 15, 17, 31, 33, 35, 37, 51, 53, 55, 57])
        place(game, 1, [12, 14, 16, 18, 32, 34, 36, 38, 52, 54, 56, 58])
        self.assertEqual(phase_weights(game.views[0]), (1.0, 1.0))

    def test_reader_counts_blocks(self):
        game = empty_game()
        place(game, 0, [41, 42, 43])
        game.place_chip(1, 44)
        game.history.append((1, Move("5H", 44), None))  # it blocked our three
        self.assertAlmostEqual(observe_opponent(game.views[0], 0), 2 / 3)
        game = empty_game()
        place(game, 0, [41, 42, 43])
        game.place_chip(1, 77)
        game.history.append((1, Move("KD", 77), None))  # it ignored our three
        self.assertAlmostEqual(observe_opponent(game.views[0], 0), 1 / 3)

    def test_logit_choice(self):
        game = self.position_with_four(0, ["4H", "2S", "3S"])
        self.assertEqual(self.choose("logit:lam=50", game), Move("4H", 45))
        game = empty_game()
        game.hands[0].extend(["2S", "3S", "4S", "5S"])
        picks = {self.choose("logit:lam=0.001", game, seed) for seed in range(30)}
        self.assertGreater(len(picks), 1)

    def test_bot_specs(self):
        self.assertEqual(make_bot("mixed:defend=0.5").defend, 0.5)
        self.assertEqual(make_bot("builder:save=1").jacks, "save")
        self.assertEqual(make_bot("mixed", values="steep").values, VALUE_SCALES["steep"])
        self.assertEqual(make_bot("mixed:values=flat", values="steep").value_scale, "flat")
        self.assertEqual(make_bot("sampler:k=2,n=3").n, 3)
        for bad in ("nope", "mixed:foo=1", "mixed:defend", "random:attack=1", "mixed:jacks=bogus",
                    "mixed:values=bogus", "mixed:infer=1", "mixed:adapt=1,read=1", "sampler:x=1",
                    "sampler:policy=random"):
            with self.assertRaises(ValueError, msg=bad):
                make_bot(bad)


class WholeGameTests(unittest.TestCase):
    def test_games_finish_and_stay_consistent(self):
        specs = ["random", "builder", "blocker", "mixed", "mixed_save"]
        for i, (a, b) in enumerate([(a, b) for a in specs for b in specs]):
            for seed in range(4):
                game = play_game(make_bot(a), make_bot(b), seed=100 * i + seed)
                game.check_consistency()
                self.assertIsNotNone(game.winner, f"{a} vs {b} seed {seed} hit the turn cap")

    def test_every_strategy_plays_whole_games(self):
        def check(game, p, move):
            game.check_consistency()

        for i, spec in enumerate(DEFAULT_BOTS):
            for seat in (0, 1):
                bots = (make_bot(spec), make_bot("mixed"))[::1 if seat == 0 else -1]
                game = play_game(*bots, seed=500 + 2 * i + seat, observer=check)
                self.assertIsNotNone(game.winner, spec)

    def test_sampler_plays_a_game(self):
        game = play_game(make_bot("sampler:k=2,n=2"), make_bot("mixed"), seed=9)
        game.check_consistency()
        self.assertIsNotNone(game.winner)

    def test_same_seed_replays_the_same_game(self):
        for spec in ("mixed", "bayes", "reader", "logit"):
            first = play_game(make_bot(spec), make_bot("random"), seed=7)
            again = play_game(make_bot(spec), make_bot("random"), seed=7)
            self.assertEqual(first.history, again.history, spec)
        other = play_game(make_bot("mixed"), make_bot("random"), seed=8)
        self.assertNotEqual(first.history, other.history)

    def test_deal_does_not_depend_on_the_bots(self):
        self.assertEqual(Game(5).hands, Game(5).hands)
        self.assertEqual(Game(5).deck, Game(5).deck)
        self.assertNotEqual(Game(5).hands, Game(6).hands)


class ScriptTests(unittest.TestCase):
    def test_duplicate_format(self):
        bots = ["a", "b", "c"]
        games = schedule(bots, deals=4, base_seed=10)
        self.assertEqual(len(games), 4 * 3 * 2 + 3 * 8)
        self.assertEqual([g[0] for g in games], list(range(len(games))))
        ab = [(s0, s1, seed) for _, s0, s1, seed in games if {s0, s1} == {"a", "b"}]
        for seed in range(10, 14):
            self.assertIn(("a", "b", seed), ab)
            self.assertIn(("b", "a", seed), ab)
        mirror = [seed for _, s0, s1, seed in games if s0 == s1 == "a"]
        self.assertEqual(mirror, list(range(10, 18)))

    def test_run_game_records_every_field(self):
        for job in ((0, "mixed", "counter", 11, 500), (1, "eager", "mixed_save", 12, 500, "flat", 1)):
            row = run_game(job)
            self.assertEqual(set(row), set(FIELDS))

    def test_hunt_search_space(self):
        import hunt
        self.assertEqual(hunt.spec_of(hunt.settings_of("mixed_save")), "mixed:jacks=save")
        self.assertEqual(hunt.canon("mixed_save"), hunt.canon("mixed:jacks=save"))
        self.assertEqual(hunt.canon("random"), "random")
        for spec in ("expert", "mixed_save", "logit"):
            for s in hunt.neighbors(hunt.settings_of(spec)):
                make_bot(hunt.spec_of(s))
        for seed in range(50):
            make_bot(hunt.spec_of(hunt.random_settings(random.Random(seed))))

    def test_pilot_games_reproduce(self):
        """The current engine replays the pilot tournament exactly (every 500th game,
        which covers every pairing and the mirror matches)."""
        path = os.path.join(HERE, "results", "full_run", "games.csv")
        if not os.path.exists(path):
            self.skipTest("results/full_run/games.csv not found")
        with open(path, newline="") as f:
            rows = [row for i, row in enumerate(csv.DictReader(f)) if i % 500 == 0]
        for old in rows:
            new = run_game((int(old["game_id"]), old["seat0"], old["seat1"], int(old["seed"]), 500))
            for key, value in old.items():
                self.assertEqual(str(new[key]), value, f"game {old['game_id']}, column {key}")


class CardLabelTests(unittest.TestCase):
    def test_cells_used_in_tests_have_the_cards_assumed(self):
        self.assertEqual(CELL_CARD[44], "5H")
        self.assertEqual(CELL_CARD[45], "4H")
        self.assertEqual(CELL_CARD[40], "9C")
        self.assertEqual(CELL_CARD[77], "KD")
        self.assertEqual(set(CARD_CELLS["5H"]), {44, 68})


if __name__ == "__main__":
    unittest.main()
