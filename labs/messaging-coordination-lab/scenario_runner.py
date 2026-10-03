import argparse
import json
import sys
from scenarios import SCENARIOS, Violation


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=SCENARIOS)
    parser.add_argument("--variant", default="correct")
    args = parser.parse_args()
    report = {"scenario": args.scenario, "variant": args.variant}
    try:
        report.update(status="pass", observed=SCENARIOS[args.scenario](args.variant))
        code = 0
    except Violation as error:
        report.update(status="rejected", error_type="Violation", code=error.code,
                      observed=error.observed)
        code = 1
    except Exception as error:
        report.update(status="error", error_type=type(error).__name__, detail=str(error))
        code = 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
