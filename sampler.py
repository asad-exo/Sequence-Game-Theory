"""The 'sampler' strategy: Monte Carlo lookahead over the hidden cards.

    python play.py sampler mixed_save --seed 3
    python tournament.py --bots mixed_save sampler --deals 100 --out results/sampler/games.csv

This is the same idea bridge programs use (Ginsberg's GIB): since the opponent's
hand is hidden, imagine many possible hands consistent with what you've seen, look
ahead in each, and pick the move that does best on average. It is known to work
well in practice even though it can't reason about information it doesn't have
(Long et al. 2010 discuss why).
"""

import random

from bots import make_bot
from scoring import WIN, best_move


class SamplerBot:
    """Lookahead by sampling the hidden cards.

    For each of the guide strategy's top `k` moves: deal the hidden cards (the
    opponent's hand and the deck) `n` times at random from the cards this player
    hasn't seen, play each game to the end with the rollout strategy on both sides,
    and count the wins. The move with the most wins is played; ties go to the move
    the guide ranked higher. All candidate moves are tried on the same n deals, so
    the comparison between them is fair.

    Cost: k * n playouts per move, so a game takes seconds rather than milliseconds.
    """

    def __init__(self, name, k=4, n=8, policy="mixed_save", plies=400):
        if k < 1 or n < 1:
            raise ValueError("k and n must be at least 1")
        if policy.partition(":")[0] in ("sampler", "random"):
            raise ValueError("the sampler's policy must be a heuristic strategy, e.g. mixed_save")
        self.name = name
        self.k = int(k)
        self.n = int(n)
        self.plies = int(plies)
        self.policy = policy
        self.guide = make_bot(policy)    # ranks the candidate moves
        self.rollout = make_bot(policy)  # plays both sides in the imagined games

    @staticmethod
    def parse(params):
        """Settings from a spec such as 'sampler:k=6,n=12,policy=counter'."""
        kwargs = {}
        for key, value in params.items():
            if key in ("k", "n", "plies"):
                kwargs[key] = int(float(value))
            elif key == "policy":
                kwargs[key] = value
            else:
                raise ValueError(f"unknown sampler setting {key!r}; use k, n, policy or plies")
        return kwargs

    def choose(self, view, p, moves, rng):
        scored = self.guide.score_moves(view, p, moves)
        ranked = sorted(scored, key=lambda item: -item[0])  # stable: ties keep their order
        if len(ranked) == 1 or ranked[0][0] >= WIN:
            return best_move(scored, rng)  # a single option, or a winning move
        candidates = [move for _, _, move in ranked[:self.k]]
        wins = [0.0] * len(candidates)
        for _ in range(self.n):
            world = view.determinize(rng)
            seed = rng.getrandbits(32)
            for i, move in enumerate(candidates):
                wins[i] += self.playout(world.clone(), p, move, seed)
        best = max(range(len(candidates)), key=lambda i: (wins[i], -i))
        return candidates[best]

    def playout(self, world, p, move, seed):
        """Play `move` for p in the imagined `world`, then let the rollout strategy
        play both sides. Returns 1 for a win, 0 for a loss, 0.5 for a draw."""
        rngs = (random.Random(seed), random.Random(seed + 1))
        world.play_move(p, move)
        limit = world.turn + self.plies
        while world.winner is None and world.turn < limit:
            q = world.to_move
            world.play_turn(self.rollout, rngs[q])
        if world.winner is None:
            return 0.5
        return 1.0 if world.winner == p else 0.0
