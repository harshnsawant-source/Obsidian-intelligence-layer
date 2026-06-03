import json

from core.llm_engine import query_llm
from core.agent_engine import route_agent
from core.agent_manager import AgentManager
from core.verification import refine
from core.verifiers import CriticVerifier
from core.log import get_logger

from capability.core.runtime_context import RuntimeContext
from capability.core.skill_loader import load_skill

from core.execution_context import SharedExecutionContext
from core.contributions import parse_contributions


log = get_logger("planner")


class Planner:

    # Decomposes a goal into a small subtask DAG, routes each subtask to an
    # agent, executes them in dependency order (feeding prior results forward),
    # and synthesises a final answer. Built entirely on top of the existing
    # router + broker + semantic memory + distillation.

    MAX_STEPS = 6

    def __init__(self, manager=None, verify=False):

        self.manager = manager or AgentManager()

        # verify=True spends a second model pass (a critic) on the synthesis —
        # the highest-value, lowest-frequency call. Default off preserves the
        # original single-pass behavior. See VERIFICATION.md section 5.3.
        self.verify = verify

    # ---- decomposition -------------------------------------------------

    def decompose(self, goal):

        agents = ", ".join(sorted(self.manager.agents))

        prompt = f"""Decompose the goal into 2 to {self.MAX_STEPS} concrete subtasks.
Return a JSON object of the form:
{{"steps": [{{"id": <int>, "task": "<what to do>", "agent": "<one of: {agents}>", "depends_on": [<ids this needs first>]}}]}}

Goal:
{goal}"""

        raw = query_llm(prompt, fmt="json", max_tokens=1200)

        steps = self._normalize(self._parse_steps(raw))

        if not steps:

            log.warning(
                "decomposition unparseable; using single-step fallback"
            )

            steps = [{
                "id": 1,
                "task": goal,
                "agent": route_agent(goal),
                "depends_on": []
            }]

        return steps

    def _parse_steps(self, raw):

        if not raw:
            return []

        text = str(raw).strip()

        data = self._loads(text)

        if data is None:

            # Fall back to extracting the first {...} or [...] block.
            for open_c, close_c in (("{", "}"), ("[", "]")):
                start = text.find(open_c)
                end = text.rfind(close_c)
                if start != -1 and end > start:
                    data = self._loads(text[start:end + 1])
                    if data is not None:
                        break

        if isinstance(data, dict):
            # Accept {"steps": [...]} or any object wrapping a list.
            if isinstance(data.get("steps"), list):
                return data["steps"]
            for value in data.values():
                if isinstance(value, list):
                    return value
            return []

        return data if isinstance(data, list) else []

    @staticmethod
    def _loads(text):
        try:
            return json.loads(text)
        except Exception:
            return None

    def _normalize(self, steps):

        normalized = []

        used_ids = set()

        next_id = 1

        for raw in steps[: self.MAX_STEPS]:

            if not isinstance(raw, dict):
                continue

            task = str(raw.get("task", "")).strip()

            if not task:
                continue

            sid = raw.get("id")

            if not isinstance(sid, int) or sid in used_ids:
                sid = next_id

            next_id = max(next_id, sid + 1)

            used_ids.add(sid)

            agent = raw.get("agent")

            if agent not in self.manager.agents:
                agent = route_agent(task)

            deps = raw.get("depends_on") or []

            if not isinstance(deps, list):
                deps = []

            deps = [d for d in deps if isinstance(d, int)]

            normalized.append({
                "id": sid,
                "task": task,
                "agent": agent,
                "depends_on": deps
            })

        # Drop dependencies that reference unknown ids (or self).
        ids = {s["id"] for s in normalized}

        for s in normalized:
            s["depends_on"] = [
                d for d in s["depends_on"] if d in ids and d != s["id"]
            ]

        return normalized

    # ---- ordering ------------------------------------------------------

    def _topo_order(self, steps):

        indegree = {s["id"]: 0 for s in steps}

        for s in steps:
            for d in s["depends_on"]:
                if d in indegree:
                    indegree[s["id"]] += 1

        ready = [s for s in steps if indegree[s["id"]] == 0]

        order = []

        seen = set()

        while ready:

            current = ready.pop(0)

            if current["id"] in seen:
                continue

            seen.add(current["id"])

            order.append(current)

            for s in steps:
                if current["id"] in s["depends_on"]:
                    indegree[s["id"]] -= 1
                    if indegree[s["id"]] == 0:
                        ready.append(s)

        # Any steps left over imply a dependency cycle: append them in the
        # original order so execution still completes.
        if len(order) < len(steps):
            for s in steps:
                if s["id"] not in seen:
                    order.append(s)

        return order

    # ---- execution -----------------------------------------------------

    def execute(self, steps):

        outputs = {}

        results = []

        for step in self._topo_order(steps):

            task = step["task"]

            dep_text = "\n\n".join(
                f"[Result of step {d}]\n{outputs[d]}"
                for d in step["depends_on"] if d in outputs
            )

            if dep_text:
                task = (
                    f"{step['task']}\n\nUse these prior results:\n{dep_text}"
                )

            output = self.manager.dispatch(step["agent"], task)

            outputs[step["id"]] = output

            results.append({
                "id": step["id"],
                "agent": step["agent"],
                "task": step["task"],
                "output": output
            })

        return results

    # ---- synthesis -----------------------------------------------------

    def synthesize(self, goal, results):

        joined = "\n\n".join(
            f"## Step {r['id']} ({r['agent']})\nTask: {r['task']}\n\n{r['output']}"
            for r in results
        )

        base_prompt = f"""Consolidate the subtask results into a single coherent answer to the goal.

Goal:
{goal}

Subtask results:
{joined}

Final consolidated answer:"""

        if not self.verify:
            return query_llm(base_prompt)

        def generate(feedback, previous):
            prompt = base_prompt
            if feedback:
                prompt += f"""

A reviewer found problems with your previous answer:
{feedback}

Revise the answer to fix them:"""
            return query_llm(prompt)

        outcome = refine(
            generate,
            goal,
            verifiers=[CriticVerifier()],
            max_tries=2,
        )

        return outcome.output

    # ---- orchestration -------------------------------------------------

    def run(self, goal):

        steps = self.decompose(goal)

        results = self.execute(steps)

        final = self.synthesize(goal, results)

        self._distill(goal, final)

        return {
            "goal": goal,
            "steps": steps,
            "results": results,
            "final": final
        }

    def _distill(self, goal, final):

        if not (isinstance(final, str) and final.strip()):
            return

        try:

            ctx = RuntimeContext()

            load_skill("knowledge_distill").execute(
                ctx,
                {"task": f"[plan] {goal}", "outcome": final}
            )

        except Exception as error:

            log.warning("plan distillation failed: %s", error)


class PlanExecutor:

    # Runs a FLAT, ordered [{task, agent}] plan SEQUENTIALLY (Phase 4), threading
    # a SharedExecutionContext through the steps. Each subtask is dispatched via
    # the manager — i.e. it runs the agent's full run() pipeline, so every
    # subtask result auto-distills into the vault with no extra work here. The
    # output is recorded into the context and fed forward (rendered into the next
    # subtask's prompt) so later steps build on earlier ones.
    #
    # This complements the DAG-based Planner above; it does not replace it.

    def __init__(self, manager=None):

        self.manager = manager or AgentManager()

    def run(self, goal, plan, progress_callback=None):

        # Returns the SharedExecutionContext (its `outputs` hold every result).
        # progress_callback(step_index, total, agent, task) is called BEFORE each
        # dispatch so a UI can show live progress; None = silent.

        ctx = SharedExecutionContext(goal)

        total = len(plan)

        for index, step in enumerate(plan, start=1):

            task = str(step.get("task", "")).strip()

            agent = step.get("agent")

            # Validate against the live pool; fall back to keyword routing.
            if agent not in self.manager.agents:
                agent = route_agent(task)

            if progress_callback:
                progress_callback(index, total, agent, task)

            framed = self._frame(task, ctx)

            output = self.manager.dispatch(agent, framed)

            ctx.record_output(agent, task, output)

            # Phase 5: extract any structured reasoning the agent emitted and
            # accumulate it, stamped with the originating agent (provenance).
            # No block -> {} -> no-op, so text-only agents are unaffected.
            ctx.merge_contributions(parse_contributions(output), agent=agent)

        return ctx

    @staticmethod
    def _frame(task, ctx):

        # Subtask receives `task + shared_execution_context` (rendered as text,
        # since agents take a string — the agent architecture is unchanged).
        # render_summary is BOUNDED + ranked so the prompt can't grow without
        # limit as findings/decisions/etc accumulate (hardening #1).
        context_text = ctx.render_summary()

        if not context_text:
            return task

        return (
            f"{task}\n\n"
            f"--- shared execution context ---\n"
            f"{context_text}\n"
            f"--- end shared execution context ---"
        )
