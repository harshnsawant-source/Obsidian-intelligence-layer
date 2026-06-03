# The eval harness: run a set of labeled cases through an INJECTED run_fn,
# grade each, aggregate, and persist a one-line summary so quality can be
# tracked across runs (a regression gate). See FEEDBACK_EVAL.md section 3.

import json
import time
from datetime import datetime
from pathlib import Path

from core.eval.graders import make_grader
from core.log import get_logger

# core/eval/harness.py -> parents[2] is src/. Default case set + run history.
SRC = Path(__file__).resolve().parents[2]
DEFAULT_CASES = SRC / "core" / "eval" / "cases.jsonl"
EVAL_RUNS = SRC.parent / "runtime" / "eval_runs.jsonl"

log = get_logger("eval")


class EvalCase:

    def __init__(self, spec):
        self.id = str(spec.get("id", "case"))
        self.task = spec.get("task", "")
        self.kind = spec.get("grader", "contains")
        self.grader = make_grader(spec)


class CaseResult:

    def __init__(self, case_id, kind, ok, score, output):
        self.id = case_id
        self.kind = kind
        self.ok = ok
        self.score = score
        self.output = output


class EvalReport:

    def __init__(self, label, results, elapsed):
        self.label = label
        self.results = results
        self.elapsed = elapsed
        self.n = len(results)
        self.passed = sum(1 for r in results if r.ok)
        self.pass_rate = (self.passed / self.n) if self.n else 0.0
        self.mean_score = (
            sum(r.score for r in results) / self.n if self.n else 0.0
        )

    def summary(self):
        return {
            "timestamp": datetime.now().isoformat(),
            "label": self.label,
            "n": self.n,
            "passed": self.passed,
            "pass_rate": round(self.pass_rate, 4),
            "mean_score": round(self.mean_score, 4),
            "elapsed_s": round(self.elapsed, 2),
        }

    def render(self):
        lines = [
            f"EVAL [{self.label}]  {self.passed}/{self.n} passed  "
            f"(pass_rate={self.pass_rate:.0%}, mean_score={self.mean_score:.2f})"
        ]
        for r in self.results:
            mark = "PASS" if r.ok else "FAIL"
            lines.append(f"  {mark}  {r.id} ({r.kind})  score={r.score:.2f}")
        return "\n".join(lines)


def load_cases(path=None):
    path = Path(path) if path else DEFAULT_CASES
    if not path.exists():
        return []
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            cases.append(EvalCase(json.loads(line)))
        except Exception as error:
            log.warning("skipping bad eval case: %s", error)
    return cases


def run_eval(cases, run_fn, label="eval", persist=True):

    # run_fn(task) -> str (the thing under test). Never raises: a case whose
    # run_fn or grader blows up is recorded as a failed case.

    started = time.time()

    results = []

    for case in cases:
        try:
            output = run_fn(case.task)
        except Exception as error:
            log.warning("case %s run_fn raised: %s", case.id, error)
            results.append(CaseResult(case.id, case.kind, False, 0.0,
                                      f"run error: {error}"))
            continue

        try:
            verdict = case.grader(case.task, output)
            results.append(CaseResult(
                case.id, case.kind, verdict.ok, verdict.score, output
            ))
        except Exception as error:
            log.warning("case %s grader raised: %s", case.id, error)
            results.append(CaseResult(case.id, case.kind, False, 0.0,
                                      f"grader error: {error}"))

    report = EvalReport(label, results, time.time() - started)

    if persist:
        _persist(report)

    return report


def _persist(report):
    try:
        EVAL_RUNS.parent.mkdir(parents=True, exist_ok=True)
        with open(EVAL_RUNS, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(report.summary()) + "\n")
    except Exception as error:
        log.warning("could not persist eval run: %s", error)


def history(limit=10):
    # Recent run summaries — the trend that makes eval a regression gate.
    if not EVAL_RUNS.exists():
        return []
    rows = []
    for line in EVAL_RUNS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]
