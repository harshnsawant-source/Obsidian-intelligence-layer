# Shared state threaded through a planned execution. The PlanExecutor owns one
# of these and mutates it as subtasks complete; every subtask is handed the
# (rendered) context so later steps build on earlier ones.
#
# Phase 4 populates `outputs` (and the derived `completed_steps`) only. The
# `findings`, `decisions`, and `artifacts` slots are reserved and intentionally
# left empty: they lock the shape of the shared state now so Phase 5 (multi-agent
# collaboration — agents reading/writing shared findings + decisions + work
# products) can fill them in WITHOUT changing the executor interface or the
# subtask contract. This is deliberate forward-compatibility, not dead code.


class SharedExecutionContext:

    def __init__(self, goal):

        self.goal = goal

        # --- populated in Phase 4 ---
        # One record per completed subtask: {"agent", "task", "output"}.
        self.outputs = []

        # Completion-ordered trail of {"task", "agent"} (cheap to scan/serialize).
        self.completed_steps = []

        # --- reserved for Phase 5 (kept empty + documented) ---
        self.findings = []      # discrete facts/insights agents surface
        self.decisions = []     # choices made, with rationale
        self.artifacts = {}     # named work products (code, files, data)

    def record_output(self, agent, task, output):

        # The single mutation Phase 4 needs: append a completed subtask result.
        self.outputs.append({
            "agent": agent,
            "task": task,
            "output": output,
        })

        self.completed_steps.append({
            "task": task,
            "agent": agent,
        })

    def render(self):

        # Textual view of the populated context, injected into each subtask. The
        # agent interface takes a string, so threading the context as rendered
        # text means a subtask "receives task + context" with NO change to the
        # existing agent architecture. Empty until the first subtask completes.

        if not self.outputs:
            return ""

        prior = "\n\n".join(
            f"[{o['agent']}] {o['task']}\n{o['output']}"
            for o in self.outputs
        )

        return f"Goal: {self.goal}\n\nResults so far:\n{prior}"
