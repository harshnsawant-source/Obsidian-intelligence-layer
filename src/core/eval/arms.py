# Benchmark V2 arms. Three execution paths, graded identically on HIDDEN tests:
#
#   A baseline        = one strong single call
#   B verified single = single call + refine() loop against PUBLIC tests
#   C verified planner = PlannerAgent.run + the SAME refine() loop against PUBLIC tests
#
# Verification is held IDENTICAL across B and C (same CodeVerifier on the public
# tests, same correction generator, same VERIFY_TRIES). The ONLY difference is
# the INITIAL generator (single call vs planner), so C-B isolates the value of
# decomposing the initial attempt with verification held constant; B-A isolates
# verification. Nothing here changes planner/routing/retrieval — arm C only
# CALLS PlannerAgent and wraps its output in the shared verify loop.

from core.llm_engine import query_llm
from core.verification import refine
from core.verifiers import CodeVerifier


# Pre-registered verification depth (1 initial generate + up to this many tries).
VERIFY_TRIES = 2


def _public_blob(public_tests):
    return "\n".join(str(t) for t in (public_tests or []))


def _solve_prompt(task, public_tests):
    return (
        "You are an expert programmer. Solve the task. "
        "Return ONLY a single python code block.\n\n"
        f"Task:\n{task}\n\n"
        f"Your solution must satisfy these examples:\n{_public_blob(public_tests)}\n\n"
        "Response:"
    )


def _correct_gen(task, public_tests):
    # Correction generator shared by B and C: re-issue the solve prompt with the
    # failing-public-test feedback appended.
    base = _solve_prompt(task, public_tests)

    def gen(feedback, previous):
        prompt = base
        if feedback:
            prompt += (
                "\n\nYour previous attempt failed these checks:\n"
                f"{previous}\n--- errors ---\n{feedback}\n"
                "Return a corrected python code block."
            )
        return query_llm(prompt, prefer_cloud=True, expects_code=True)

    return gen


def _verified_run(init_gen, correct_gen, task, public_tests, tries=VERIFY_TRIES):
    # init_gen() -> first attempt; correct_gen(feedback, previous) -> retries.
    # Verifier = run the PUBLIC tests in the sandbox (hidden tests are grading-
    # only). This is the identical verification used by both B and C.
    verifier = CodeVerifier(execute=True, test=_public_blob(public_tests))

    def generate(feedback, previous):
        if previous is None:
            return init_gen()
        return correct_gen(feedback, previous)

    return refine(generate, task, verifiers=[verifier], max_tries=tries).output


# ---- the three arms (each takes the task text + the case's public tests) ----

def arm_baseline(task, public_tests):
    return query_llm(_solve_prompt(task, public_tests),
                     prefer_cloud=True, expects_code=True)


def arm_verified_single(task, public_tests):
    base = _solve_prompt(task, public_tests)
    init = lambda: query_llm(base, prefer_cloud=True, expects_code=True)
    return _verified_run(init, _correct_gen(task, public_tests), task, public_tests)


def arm_verified_planner(task, public_tests):
    # Lazy import: planner_agent imports route_agent from agent_engine.
    from agents.planner_agent import PlannerAgent

    planner_task = (
        f"{task}\n\nYour solution must satisfy these examples:\n"
        f"{_public_blob(public_tests)}\n"
        "Return the final answer as a single python code block."
    )
    init = lambda: PlannerAgent().run(planner_task)
    return _verified_run(init, _correct_gen(task, public_tests), task, public_tests)


ARMS = {
    "A": arm_baseline,
    "B": arm_verified_single,
    "C": arm_verified_planner,
}
