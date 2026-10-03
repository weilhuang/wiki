"""Original, finite arithmetic model. No telemetry collector or production SLO."""
from dataclasses import dataclass
from fractions import Fraction
from math import ceil


@dataclass(frozen=True)
class Event:
    group: str
    outcome: str
    milliseconds: int
    eligible: bool = True


def fixture():
    # Counts describe synthetic external attempts, not internal retry spans.
    return ([Event("A", "ok", 100)] * 90
            + [Event("A", "ok", 400)] * 8
            + [Event("A", "timeout", 1000)] * 2
            + [Event("B", "ok", 100)]
            + [Event("B", "timeout", 1000)] * 9
            + [Event("health", "ok", 1, False)] * 5)


def measure(events, *, complete=True, threshold=300, variant="correct"):
    if not complete and variant != "missing-is-zero":
        return {"status": "unknown", "total": None, "good": None, "ratio": None}
    selected = [e for e in events if e.eligible or variant == "include-health"]
    if variant == "drop-timeouts":
        selected = [e for e in selected if e.outcome != "timeout"]
    good = sum(e.outcome == "ok" and
               (e.milliseconds < threshold if variant == "strict-threshold"
                else e.milliseconds <= threshold) for e in selected)
    count = len(selected)
    ratio = Fraction(good, count) if count else None
    if not count and variant == "zero-is-perfect":
        ratio = Fraction(1)
    if count and variant == "mean-ratios":
        groups = sorted({e.group for e in selected})
        ratio = sum((measure([e for e in selected if e.group == group])["ratio"]
                     for group in groups), Fraction(0)) / len(groups)
    return {"status": "observed" if count else "no-traffic",
            "total": count, "good": good, "ratio": ratio}


def budget(total, bad, target=Fraction(99, 100), variant="correct"):
    if not 0 <= bad <= total or not 0 < target < 1:
        raise ValueError("invalid budget inputs")
    allowed = total * (target if variant == "use-target-as-budget" else 1 - target)
    return {"allowed": allowed, "remaining": allowed - bad,
            "burn": Fraction(bad, total) / (1 - target) if total else None}


def quantile(values, q=Fraction(95, 100)):
    if not values or not 0 < q <= 1:
        raise ValueError("nonempty sample and 0 < q <= 1 required")
    return sorted(values)[ceil(q * len(values)) - 1]


def merged_p95(groups, variant="correct"):
    if variant == "mean-p95":
        return sum(quantile(g) for g in groups) / len(groups)
    if variant == "weighted-p95":
        return Fraction(sum(quantile(g) * len(g) for g in groups),
                        sum(map(len, groups)))
    return quantile([value for group in groups for value in group])


def buckets(values, bounds=(100, 300, 1000)):
    # Cumulative buckets, including the boundary. All sample values <= 1000.
    if any(v < 0 or v > bounds[-1] for v in values):
        raise ValueError("sample outside finite teaching buckets")
    return tuple(sum(v <= bound for v in values) for bound in bounds)


def merge_buckets(groups, variant="correct"):
    if not groups or any(len(g) != len(groups[0]) for g in groups):
        raise ValueError("same ordered bucket layout required")
    if variant == "average-buckets":
        return tuple(Fraction(sum(xs), len(groups)) for xs in zip(*groups))
    return tuple(map(sum, zip(*groups)))


def sampled_error_ratio(variant="correct"):
    # Known deterministic retention: all 10 errors, 10 of 90 successes.
    # This is a fixture about selection bias, not a probability estimator.
    population = ["ok"] * 90 + ["error"] * 10
    retained = population[:10] + [outcome for outcome in population if outcome == "error"]
    selected = retained if variant == "sample-is-population" else population
    return Fraction(sum(outcome == "error" for outcome in selected), len(selected))
