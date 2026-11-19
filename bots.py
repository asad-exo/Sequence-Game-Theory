"""Bot strategies.

A bot is any object with a `name` and a method
    choose(view, player, moves, rng) -> Move
that returns one of `moves`. `view` is a game.PlayerView: the board, the bot's own
hand and everything played face up, never the opponent's cards. Use `rng` for any
randomness (never the global `random` module), so every game can be replayed
exactly from its seed. Bots must not keep game state on themselves (one bot object
plays many games, and both seats in mirror matches); use `view.notes` instead.

Every strategy except `random` and `sampler` is a HeuristicBot: it scores each
legal move on the 192 five-in-a-row lines through its space (see scoring.py),
    score = attack * gain + defend * block  (+ optional features)
and plays the best one. Each named strategy is a preset of HeuristicBot settings,
so new variants are one spec away, e.g. "mixed:defend=0.5" or "counter:fork=1".
"""

from board import JACKS, TWO_EYED_JACKS
from scoring import (CENTRALITY, EAGER_BONUS, VALUE_SCALES, CardInfo,
                     adaptive_weights, best_move, counted_placement_value,
                     counted_removal_value, critical_cells, fork_gaps, hand_bonus,
                     inferred_gap_chances, logit_choice, observe_opponent,
                     phase_weights, placement_value, removal_value)

JACK_POLICIES = ("greedy", "save", "save_wild", "save_remove", "eager")


class RandomBot:
    """Picks one of its playable cards at random, then a random space for it."""

    def __init__(self, name="random"):
        self.name = name

    def choose(self, view, p, moves, rng):
        by_card = {}
        for move in moves:
            by_card.setdefault(move.card, []).append(move)
        return rng.choice(by_card[rng.choice(sorted(by_card))])


class HeuristicBot:
    """One-move-ahead strategy: scores every legal move and plays the best one.

    Settings (the defaults give the 'mixed' bot):
      attack, defend  weights on building your lines and blocking theirs
      jacks           'greedy'      play a Jack whenever it scores best
                      'save'        keep both kinds for completing or stopping a sequence
                      'save_wild'   keep only two-eyed Jacks that way
                      'save_remove' keep only one-eyed Jacks that way
                      'eager'       play Jacks first unless something urgent is on
      values          line-value scale: 'linear', 'flat', 'default' or 'steep'
      center          bonus per move for central spaces (centrality 0.15-1 times this)
      fork            bonus, in fours' worth, for each threat beyond the first after the move
      hand            1 = hand management (scoring.hand_bonus)
      count           1 = card counting (scoring.CardInfo)
      infer           1 = also infer missing cards from the opponent's last turn (needs count)
      adapt           1 = attack/defend set by who is ahead (scoring.adaptive_weights)
      phase           1 = attack/defend slide from building to blocking as the board fills
      read            1 = defend set by how often the opponent blocks (scoring.observe_opponent)
      lam             > 0 = logit choice: move probability proportional to exp(lam * score)
    """

    def __init__(self, name, attack=1.0, defend=1.0, jacks="greedy", values="default",
                 center=0.0, fork=0.0, hand=0.0, count=0, infer=0, adapt=0, phase=0,
                 read=0, lam=0.0):
        if jacks not in JACK_POLICIES:
            raise ValueError(f"jacks must be one of {', '.join(JACK_POLICIES)}, not {jacks!r}")
        if values not in VALUE_SCALES:
            raise ValueError(f"values must be one of {', '.join(VALUE_SCALES)}, not {values!r}")
        if infer and not count:
            raise ValueError("infer=1 needs count=1")
        if sum(1 for flag in (adapt, phase, read) if flag) > 1:
            raise ValueError("use at most one of adapt, phase and read")
        if lam < 0:
            raise ValueError("lam must be 0 or more")
        self.name = name
        self.attack = float(attack)
        self.defend = float(defend)
        self.jacks = jacks
        self.value_scale = values
        self.values = VALUE_SCALES[values]
        self.center = float(center)
        self.fork = float(fork)
        self.hand = float(hand)
        self.count = bool(count)
        self.infer = bool(infer)
        self.adapt = bool(adapt)
        self.phase = bool(phase)
        self.read = bool(read)
        self.lam = float(lam)

    def weights(self, view, p):
        """(attack, defend) for this turn."""
        if self.adapt:
            return adaptive_weights(view, p)
        if self.phase:
            return phase_weights(view)
        if self.read:
            defensiveness = observe_opponent(view, p)
            return self.attack, 0.5 + (1.0 - defensiveness)
        return self.attack, self.defend

    def score_moves(self, view, p, moves):
        """[(score, is_jack, move)] for the moves this bot is willing to play.

        Jack moves held back by a saving policy are returned only when nothing else
        is legal."""
        attack, defend = self.weights(view, p)
        values = self.values
        save_wild = self.jacks in ("save", "save_wild")
        save_remove = self.jacks in ("save", "save_remove")
        allowed = None
        if ((save_wild and any(m.card in TWO_EYED_JACKS for m in moves))
                or (save_remove and any(m.remove for m in moves))):
            allowed = critical_cells(view, p)
        info = None
        if self.count:
            info = CardInfo(view, p)
            if self.infer:
                info.inferred = inferred_gap_chances(view, p, info)
        existing_gaps = view.threat_gaps(p) if self.fork else None
        hand = view.hand if self.hand else None
        cache, fork_cache = {}, {}

        def score(move):
            if move.remove:
                if info is None:
                    gain, block, _ = removal_value(view, p, move.cell, values)
                else:
                    gain, block, _ = counted_removal_value(view, p, move.cell, values, info)
            else:
                cached = cache.get(move.cell)
                if cached is None:
                    if info is None:
                        cached = placement_value(view, p, move.cell, values)
                    else:
                        cached = counted_placement_value(view, p, move.cell, values, info)
                    cache[move.cell] = cached
                gain, block = cached[0], cached[1]
            total = attack * gain + defend * block
            if not move.remove:
                if self.center:
                    total += self.center * CENTRALITY[move.cell]
                if self.fork:
                    extra = fork_cache.get(move.cell)
                    if extra is None:
                        gaps = fork_gaps(view, p, move.cell, existing_gaps)
                        extra = fork_cache[move.cell] = max(0, len(gaps) - 1)
                    total += self.fork * values[4] * extra
            if self.hand:
                total += self.hand * hand_bonus(view, p, move, values, hand)
            if self.jacks == "eager" and move.card in JACKS:
                total += EAGER_BONUS
            return total

        options, held = [], []
        for move in moves:
            jack = move.card in JACKS
            if jack and allowed is not None and (save_remove if move.remove else save_wild):
                wild_cells, removable = allowed
                if move.cell not in (removable if move.remove else wild_cells):
                    held.append(move)  # scored only if nothing else can be played
                    continue
            options.append((score(move), jack, move))
        return options or [(score(move), True, move) for move in held]

    def choose(self, view, p, moves, rng):
        scored = self.score_moves(view, p, moves)
        if self.lam > 0:
            return logit_choice(scored, self.lam, rng)
        return best_move(scored, rng)


# ---- named strategies ------------------------------------------------------------

# Each preset is a set of HeuristicBot settings on top of the defaults (attack 1,
# defend 1, greedy Jacks, default values). New ideas build on mixed_save, the pilot's
# champion, so comparing one with mixed_save isolates what the idea adds.
PRESETS = {
    # baselines
    "builder": dict(attack=1.0, defend=0.0),
    "blocker": dict(attack=0.2, defend=1.0),
    "mixed": dict(),
    # Jack timing
    "mixed_save": dict(jacks="save"),
    "save_wild": dict(jacks="save_wild"),
    "save_remove": dict(jacks="save_remove"),
    "eager": dict(jacks="eager"),
    # position, tactics and hand management
    "center": dict(jacks="save", center=10.0),
    "forker": dict(jacks="save", fork=1.0),
    "planner": dict(jacks="save", hand=1.0),
    # information
    "counter": dict(jacks="save", count=1),
    "bayes": dict(jacks="save", count=1, infer=1),
    # adaptation
    "adaptive": dict(jacks="save", adapt=1),
    "phase": dict(jacks="save", phase=1),
    "reader": dict(jacks="save", read=1),
    # bounded rationality
    "logit": dict(jacks="save", lam=1.0),
    # everything that combines cleanly
    "expert": dict(jacks="save", fork=1.0, hand=1.0, count=1, infer=1, adapt=1),
}

DESCRIPTIONS = {
    "random": "plays a random card on a random open space",
    "builder": "only extends its own lines",
    "blocker": "mostly blocks",
    "mixed": "balances building and blocking",
    "mixed_save": "mixed, keeping both kinds of Jack for completing or stopping a sequence",
    "save_wild": "mixed, keeping only two-eyed Jacks",
    "save_remove": "mixed, keeping only one-eyed Jacks",
    "eager": "mixed, spending Jacks as soon as it can",
    "center": "mixed_save plus extra weight on central spaces",
    "forker": "mixed_save plus a bonus for creating two threats at once",
    "planner": "mixed_save plus hand management",
    "counter": "mixed_save plus card counting",
    "bayes": "counter plus inference about the opponent's hand",
    "adaptive": "mixed_save, defending more when behind and attacking more when ahead",
    "phase": "mixed_save, building early and defending late",
    "reader": "mixed_save, defending more against opponents that rarely block",
    "logit": "mixed_save with logit (noisy) choice, lambda = 1",
    "expert": "mixed_save with forks, counting, inference, hand management and adaptation",
    "sampler": "Monte Carlo lookahead: deals the hidden cards at random and plays moves out",
}

ROSTERS = {
    "pilot": ["random", "builder", "blocker", "mixed", "mixed_save"],
    "jacks": ["mixed", "eager", "save_wild", "save_remove", "mixed_save"],
    "ideas": ["mixed_save", "center", "forker", "planner", "counter", "bayes",
              "adaptive", "phase", "reader", "logit", "expert"],
    "full": ["random", "builder", "blocker", "mixed", "mixed_save", "save_wild",
             "save_remove", "eager", "center", "forker", "planner", "counter", "bayes",
             "adaptive", "phase", "reader", "logit", "expert"],
}
DEFAULT_BOTS = ROSTERS["full"]

_FLOAT_PARAMS = {"attack", "defend", "center", "fork", "hand", "lam"}
_FLAG_PARAMS = {"count", "infer", "adapt", "phase", "read"}
_TEXT_PARAMS = {"jacks", "values"}


def parse_spec(spec):
    """'mixed:defend=0.5,save=1' -> ('mixed', {'defend': '0.5', 'save': '1'})"""
    base, _, text = spec.partition(":")
    params = {}
    for item in filter(None, text.split(",")):
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise ValueError(f"bad parameter {item!r} in {spec!r}; write name=value")
        params[key.strip()] = value.strip()
    return base.strip(), params


def heuristic_settings(spec, values=None):
    """The full HeuristicBot settings for a spec such as 'counter:fork=1'.

    `values` is the line-value scale to use when the spec doesn't name one."""
    base, params = parse_spec(spec)
    if base not in PRESETS:
        raise ValueError(f"unknown strategy {base!r}; choose from random, sampler, {', '.join(PRESETS)}")
    settings = dict(PRESETS[base])
    if values is not None:
        settings.setdefault("values", values)
    for key, value in params.items():
        if key == "save":  # older spelling: save=1 means jacks=save
            settings["jacks"] = "save" if float(value) else "greedy"
        elif key in _FLOAT_PARAMS:
            settings[key] = float(value)
        elif key in _FLAG_PARAMS:
            settings[key] = int(float(value) != 0)
        elif key in _TEXT_PARAMS:
            settings[key] = value
        else:
            names = sorted(_FLOAT_PARAMS | _FLAG_PARAMS | _TEXT_PARAMS | {"save"})
            raise ValueError(f"unknown setting {key!r} in {spec!r}; use {', '.join(names)}")
    return settings


def make_bot(spec, values=None):
    """Build a bot from a spec: a strategy name, optionally with settings, e.g.
    "mixed", "mixed:defend=0.5,jacks=save", "logit:lam=0.3", "sampler:k=6,n=12".

    `values` sets the line-value scale for heuristic bots whose spec doesn't."""
    base, params = parse_spec(spec)
    if base == "random":
        if params:
            raise ValueError("the random bot takes no settings")
        return RandomBot(spec)
    if base == "sampler":
        from sampler import SamplerBot  # imported here to avoid a circular import
        return SamplerBot(spec, **SamplerBot.parse(params))
    return HeuristicBot(spec, **heuristic_settings(spec, values))
