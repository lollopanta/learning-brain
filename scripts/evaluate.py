"""Run ten synthetic mechanical scenarios. Never report these as semantic pilot scores."""

import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))


def main():
    cases = json.loads((ROOT / "evals/cases.json").read_text())
    outcomes = []
    for case in cases:
        suite = unittest.TestLoader().loadTestsFromNames(
            ["test_workflow.WorkflowTests." + test for test in case["tests"]]
        )
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=0).run(suite)
        outcomes.append(
            {"id": case["id"], "passed": result.wasSuccessful(), "tests": result.testsRun}
        )
        if not result.wasSuccessful():
            print(output.getvalue(), file=sys.stderr)
    print(
        json.dumps(
            {
                "suite": "synthetic-mechanics-v1",
                "cases": outcomes,
                "passed": sum(case["passed"] for case in outcomes),
                "total": len(outcomes),
                "semantic_precision": None,
                "human_pilot": "not run",
            },
            indent=2,
        )
    )
    return 0 if all(case["passed"] for case in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
