"""Hidden "bad luck protection" for the superlegendary tier of the gacha.

Every gacha roll that doesn't give a superlegendary raises, a little, the chance that the next one does, and
lowers by the same amount the chance of a normal legendary. So the "top slot" (superlegendary + legendary,
about 5.19 % per roll) never changes: the protection only moves weight from one to the other, and common, rare
and epic keep exactly their usual absolute chances. When the superlegendary is obtained the streak goes back
to 0. The per-user streak lives in `Profile.gacha_pity`.

It is deliberately not shown anywhere: the gacha page keeps listing the base odds, and the field isn't in the
admin (institute leads can open the profile admin).

Tuning: `SUPERLEGENDARY_PITY_STEPS` is the only knob. Each pair is (streak from which it applies, chance added
per roll without a superlegendary). The chance is capped so the legendary can't go below 0.
"""
import random

from judge.models import Achievement

# Chance of each normal tier on a roll, before the separate superlegendary draw. Shared with the odds shown on
# the gacha page, so the page and the roll can't drift apart.
NORMAL_TIER_CHANCES = ((Achievement.QUALITY_COMMON, 0.65), (Achievement.QUALITY_RARE, 0.20),
                       (Achievement.QUALITY_EPIC, 0.10), (Achievement.QUALITY_LEGENDARY, 0.05))

# (from this many rolls without a superlegendary, chance added per roll). 0.00005 = +0.005 percentage points.
# Every 100 dry rolls the slope doubles; the cap is reached after ~375 dry rolls.
SUPERLEGENDARY_PITY_STEPS = ((0, 0.00005), (100, 0.0001), (200, 0.0002))

_BASE = Achievement.SUPERLEGENDARY_CHANCE
_LEGENDARY_BASE = dict(NORMAL_TIER_CHANCES)[Achievement.QUALITY_LEGENDARY]
# Superlegendary + legendary, as absolute chances at streak 0. The protection keeps this constant.
TOP_SLOT = _BASE + (1 - _BASE) * _LEGENDARY_BASE


def superlegendary_chance(streak):
    """Chance that a roll is a superlegendary after `streak` rolls without one (for a user who can still get one)."""
    streak = max(0, int(streak or 0))
    chance = _BASE
    for index, (start, slope) in enumerate(SUPERLEGENDARY_PITY_STEPS):
        end = SUPERLEGENDARY_PITY_STEPS[index + 1][0] if index + 1 < len(SUPERLEGENDARY_PITY_STEPS) else streak
        chance += max(0, min(streak, end) - start) * slope
    return min(chance, TOP_SLOT)


def normal_tier_weights(streak=None):
    """[(quality, weight)] for the draw among the four normal tiers, used when the superlegendary draw failed.

    The weights are the *absolute* chances of each tier at that streak (they are only proportional to the
    conditional chances once the superlegendary has failed, which is all `random.choices` needs).
    `streak=None` is for someone who already owns every superlegendary: no protection, plain 65/20/10/5.
    """
    if streak is None:
        return list(NORMAL_TIER_CHANCES)
    weights = [(quality, chance * (1 - _BASE)) for quality, chance in NORMAL_TIER_CHANCES
               if quality != Achievement.QUALITY_LEGENDARY]
    weights.append((Achievement.QUALITY_LEGENDARY, max(0.0, TOP_SLOT - superlegendary_chance(streak))))
    return weights


def pick_normal_quality(streak=None, rng=random):
    weights = normal_tier_weights(streak)
    return rng.choices([quality for quality, _ in weights], [weight for _, weight in weights])[0]
