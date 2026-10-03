"""Run finite scenarios in one Python process; verify exact counterexamples.

Use an external total deadline: timeout 10s python3 -B verify.py
No subprocesses or real service lifecycle is exercised here.
"""
import argparse
import json
import platform
import sys
from fractions import Fraction
from pathlib import Path

from lifecycle import Process, endpoint_conditions
from signals import (Event, budget, buckets, fixture, measure, merge_buckets,
                     merged_p95, quantile, sampled_error_ratio)


def encode(value):
    if isinstance(value, Fraction):
        return str(value)
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    return value


class Mismatch(Exception):
    def __init__(self, code, expected, actual):
        self.evidence = {"code": code, "expected": encode(expected),
                         "actual": encode(actual)}
        super().__init__(json.dumps(self.evidence, sort_keys=True))


def equal(code, actual, expected):
    if actual != expected:
        raise Mismatch(code, expected, actual)


def counts(variant):
    result = measure(fixture(), variant=variant)
    equal("eligible-counts", (result["total"], result["good"]), (110, 91))
    equal("pooled-ratio", result["ratio"], Fraction(91, 110))
    return encode(result)


def threshold(variant):
    events = [Event("A", "ok", t) for t in (250, 300, 301)]
    result = measure(events, variant=variant)
    equal("inclusive-boundary", result["good"], 2)
    equal("inclusive-ratio", result["ratio"], Fraction(2, 3))
    # A fast error is still bad; a slower successful request is also bad.
    equal("success-and-speed", measure([Event("A", "error", 1),
          Event("A", "ok", 400)])["good"], 0)
    return encode(result)


def empty(variant):
    result = measure([], variant=variant)
    equal("empty-ratio", result["ratio"], None)
    equal("empty-state", result["status"], "no-traffic")
    return result


def missing(variant):
    result = measure([], complete=False, variant=variant)
    equal("unknown-state", result["status"], "unknown")
    equal("unknown-count", result["total"], None)
    return result


def budget_case(variant):
    result = budget(110, 19, variant=variant)
    equal("allowed-bad-events", result["allowed"], Fraction(11, 10))
    equal("budget-overrun", result["remaining"], Fraction(-179, 10))
    equal("burn-rate", result["burn"], Fraction(190, 11))
    equal("zero-budget-burn", budget(0, 0)["burn"], None)
    return encode(result)


def percentile(variant):
    result = merged_p95([[100] * 100, [1000] * 10], variant=variant)
    equal("pooled-p95", result, 1000)
    equal("rank-ceiling", quantile(list(range(1, 22))), 20)
    return {"pooled_p95_ms": result, "rank_for_21": 20}


def histogram(variant):
    result = merge_buckets([buckets([100] * 100), buckets([1000] * 10)], variant)
    equal("summed-buckets", result, (100, 100, 110))
    # The only justified p95 interval is (300, 1000], not a precise value.
    equal("threshold-fraction", Fraction(result[1], result[-1]), Fraction(10, 11))
    alternative = [100] * 100 + [500] * 10
    equal("same-buckets-different-distribution", buckets(alternative), (100, 100, 110))
    equal("different-exact-p95", quantile(alternative), 500)
    return {"cumulative": encode(result), "p95_interval_ms": "(300,1000]",
            "same_buckets_alternative_exact_p95_ms": 500}


def sampling(variant):
    result = sampled_error_ratio(variant)
    equal("population-error-ratio", result, Fraction(1, 10))
    return {"population": str(result), "retained": "1/2"}


def propagate(variant):
    p = Process(variant)
    p.startup_complete()
    equal("old-admit", p.admit("old"), "accepted")
    p.delete(0, 10)
    p.publish_endpoint()
    equal("route-not-yet-refreshed", p.router_has_endpoint, True)
    equal("terminating-endpoint", p.endpoint,
          {"ready": False, "serving": True, "terminating": True})
    p.stop_admission()
    equal("stale-route-rejected", p.admit("late"), "rejected")
    p.refresh_router()
    equal("refreshed-route", p.admit("new"), "not-routed")
    equal("existing-connection-rejected", p.admit("keepalive", existing_connection=True),
          "rejected")
    equal("no-rejected-side-effects", sorted(p.active), ["old"])
    equal("drain-old", p.finish("old"), "completed")
    p.close_dependency()
    equal("normal-exit", p.exit_clean(), "clean")
    equal("normal-final-state", (p.completed, p.rejected, p.close_count, p.uncertain),
          (["old"], ["late", "keepalive"], 1, []))
    return {"completed": p.completed, "rejected": p.rejected, "close_count": p.close_count}


def readiness_window(variant):
    p = Process(variant)
    equal("startup-not-routed", p.admit("before-start"), "not-routed")
    p.startup_complete()
    p.ready = False  # Simulated application signal; deliberately no gate action.
    p.publish_endpoint()
    equal("stale-arrival-before-stop", p.admit("pre-stop"), "accepted")
    p.stop_admission()
    p.finish("pre-stop")
    p.close_dependency()
    equal("readiness-window-cleanup", p.exit_clean(), "clean")
    return {"completed": p.completed}


def close_active(variant):
    p = Process(variant)
    p.startup_complete()
    p.admit("in-flight")
    p.stop_admission()
    result = p.close_dependency()
    equal("dependency-held-while-active", (result, p.dependency_open, p.close_count),
          ("busy", True, 0))
    equal("in-flight-completes", p.finish("in-flight"), "completed")
    p.close_dependency()
    equal("active-cleanup", p.exit_clean(), "clean")
    return {"completed": p.completed, "close_count": p.close_count}


def close_twice(variant):
    p = Process(variant)
    p.startup_complete()
    p.stop_admission()
    p.close_dependency()
    p.close_dependency()
    equal("close-once", p.close_count, 1)
    equal("close-cleanup", p.exit_clean(), "clean")
    return {"close_count": p.close_count}


def gate_twice(variant):
    p = Process(variant)
    p.startup_complete()
    p.stop_admission()
    p.stop_admission()
    equal("gate-remains-closed", p.accepting, False)
    equal("repeated-stop-rejects", p.admit("late"), "rejected")
    p.close_dependency()
    equal("gate-cleanup", p.exit_clean(), "clean")
    return {"accepting": p.accepting, "rejected": p.rejected}


def deadline_case(variant):
    p = Process(variant)
    p.startup_complete()
    p.admit("unfinished")
    p.delete(0, 10)
    p.hook_finished(6)
    equal("single-grace-deadline", p.deadline, 10)
    p.stop_admission()
    result = p.expire(10)
    equal("forced-is-not-clean", result, "forced")
    equal("forced-state", (p.exited, p.forced, sorted(p.active), p.completed,
                           p.uncertain, p.close_count),
          (True, True, [], [], ["unfinished"], 0))
    equal("late-completion-cannot-claim-success", p.finish("unfinished"), "not-active")
    return {"deadline": p.deadline, "exit": result, "uncertain": p.uncertain,
            "application_cleanup_ran": False}


def conditions(variant):
    result = endpoint_conditions(True, True, variant=variant)
    equal("terminating-not-ready", result["ready"], False)
    exception = endpoint_conditions(False, True, True, variant)
    equal("publish-not-ready-exception", exception["ready"], True)
    equal("serving-retains-readiness", exception["serving"], False)
    return {"ordinary": result, "exception": exception}


CASES = {"counts": counts, "threshold": threshold, "empty": empty,
         "missing": missing, "budget": budget_case, "percentile": percentile,
         "histogram": histogram, "sampling": sampling, "propagate": propagate,
         "readiness-window": readiness_window, "close-active": close_active,
         "close-twice": close_twice, "gate-twice": gate_twice,
         "deadline": deadline_case, "conditions": conditions}


# Fixed independent expected failure identities. A RuntimeError, syntax error,
# wrong failed invariant or unexpected success cannot satisfy these records.
MUTANTS = {
    "include-health": ("counts", "eligible-counts", [110, 91], [115, 96]),
    "drop-timeouts": ("counts", "eligible-counts", [110, 91], [99, 91]),
    "mean-ratios": ("counts", "pooled-ratio", "91/110", "1/2"),
    "strict-threshold": ("threshold", "inclusive-boundary", 2, 1),
    "zero-is-perfect": ("empty", "empty-ratio", None, "1"),
    "missing-is-zero": ("missing", "unknown-state", "unknown", "no-traffic"),
    "use-target-as-budget": ("budget", "allowed-bad-events", "11/10", "1089/10"),
    "mean-p95": ("percentile", "pooled-p95", 1000, 550.0),
    "weighted-p95": ("percentile", "pooled-p95", 1000, "2000/11"),
    "average-buckets": ("histogram", "summed-buckets", [100, 100, 110],
                        ["50", "50", "55"]),
    "sample-is-population": ("sampling", "population-error-ratio", "1/10", "1/2"),
    "instant-propagation": ("propagate", "route-not-yet-refreshed", True, False),
    "early-close": ("close-active", "dependency-held-while-active",
                    ["busy", True, 0], ["closed", False, 1]),
    "double-close": ("close-twice", "close-once", 1, 2),
    "toggle-gate": ("gate-twice", "gate-remains-closed", False, True),
    "restart-grace": ("deadline", "single-grace-deadline", 10, 16),
    "force-is-clean": ("deadline", "forced-is-not-clean", "forced", "clean"),
    "ignore-terminating": ("conditions", "terminating-not-ready", False, True),
    "ignore-publish-exception": ("conditions", "publish-not-ready-exception", True, False),
}


def expected_evidence(spec):
    return {"code": spec[1], "expected": spec[2], "actual": spec[3]}


def is_target(error, spec):
    return type(error) is Mismatch and error.evidence == expected_evidence(spec)


def run_mutant(name):
    spec = MUTANTS[name]
    try:
        CASES[spec[0]](name)
    except Exception as error:
        if is_target(error, spec):
            return {"mutant": name, "case": spec[0], "status": "target-rejected",
                    "failure": error.evidence}
        raise RuntimeError(f"wrong failure identity for {name}: {type(error).__name__}") from error
    raise RuntimeError(f"unexpected mutant success: {name}")


def verifier_probes():
    spec = MUTANTS["mean-ratios"]
    probes = [RuntimeError("pooled-ratio"), None,
              Mismatch("other-invariant", "91/110", "1/2"),
              Mismatch("pooled-ratio", "wrong-expected", "1/2"),
              Mismatch("pooled-ratio", "91/110", "wrong-actual")]
    equal("verifier-refuses-unrelated-failures", [is_target(x, spec) for x in probes],
          [False] * 5)
    return ["wrong-exception", "unexpected-success", "wrong-code",
            "wrong-expected", "wrong-actual"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutant", choices=sorted(MUTANTS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.mutant:
        print(json.dumps(run_mutant(args.mutant), ensure_ascii=False, sort_keys=True))
        return 2  # Expected rejection, not an execution/setup failure.
    correct = [{"case": name, "status": "pass", "observed": fn("correct")}
               for name, fn in CASES.items()]
    mutants = [run_mutant(name) for name in MUTANTS]
    report = {"status": "pass", "runtime": platform.python_version(),
              "scope": "finite arithmetic and sequential lifecycle model only",
              "correct": correct, "mutants": mutants, "verifier_probes": verifier_probes()}
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(f"{len(correct)} model cases passed; {len(mutants)} exact target rejections; "
          f"{len(report['verifier_probes'])} unrelated outcomes refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())
