import sys
from datetime import datetime

# Models (esp. the cloud coder model) can emit unicode the Windows console's
# default cp1252 encoding cannot print, which would raise UnicodeEncodeError.
# Force UTF-8 output so printing model responses never crashes the menu.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from core.retrieval_engine import (
    run_retrieval_scan
)

from core.runtime_engine import (
    generate_runtime_prompt
)

from core.workflow_engine import (
    classify_workflow
)

from core.diagnostics_engine import (
    run_diagnostics
)

from core.memory_engine import (
    store_memory
)

from core.recall_engine import (
    recall_recent_memory
)

from core.context_matcher import (
    match_context
)

from core.session_state import (
    update_session_state
)

from core.insight_engine import (
    generate_insights
)

from core.objective_engine import (
    add_objective,
    show_objectives
)

from core.task_engine import (
    create_task,
    view_tasks
)

from core.agent_engine import (
    execute_agent_task,
    show_agent_status,
    route_agent
)

from core.agent_memory import (
    store_agent_memory,
    show_agent_memory
)

from capability.core.runtime_context import (
    RuntimeContext
)

from capability.core.skill_loader import (
    load_skill
)

from core.planner import (
    Planner
)


def show_banner():

    print("\n")
    print("=" * 50)
    print(" OBSIDIAN INTELLIGENCE LAYER ")
    print("=" * 50)

    print(
        f"\nSession Started: {datetime.now()}"
    )


def show_menu():

    print("\nAVAILABLE OPERATIONS:\n")

    print("1. Generate Context Package")

    print("2. Generate Runtime Prompt")

    print("3. Workflow Classification")

    print("4. Run Diagnostics")

    print("5. Recall Workflow Memory")

    print("6. Contextual Memory Search")

    print("7. Generate Operational Insights")

    print("8. Add Objective")

    print("9. View Objectives")

    print("10. Create Task")

    print("11. View Tasks")

    print("12. Show Agent Network")

    print("13. View Agent Memory")

    print("14. Execute Agent Task")

    print("15. Plan & Execute Goal")

    print("16. Ingest Document")

    print("17. Ask Documents (RAG)")

    print("18. View Escalations")

    print("19. Run Eval Suite")

    print("20. Curate Vault (prune + dedupe)")

    print("21. Run Tool Agent")

    print("22. Run Lift Benchmark")

    print("23. Index Obsidian Vault")

    print("24. Ask Obsidian Notes")

    print("25. Exit")


def generate_context_package():

    print(
        "\n=== CONTEXT PACKAGE ===\n"
    )

    task = input(
        "Describe operational task:\n\n"
    )

    workflow = classify_workflow(task)

    assigned_agent = route_agent(task)

    store_memory(task, workflow)

    store_agent_memory(
        assigned_agent,
        task
    )

    update_session_state(
        task,
        workflow
    )

    print(
        f"\nDetected Workflow: {workflow}"
    )

    print(
        f"\nAssigned Agent: {assigned_agent}"
    )

    execute_agent_task(task)

    print(
        "\nRunning retrieval scan...\n"
    )

    run_retrieval_scan()

    print(
        "\nSearching contextual memory...\n"
    )

    match_context(task)

    print(
        "\nContext package generated."
    )


def workflow_classification():

    task = input(
        "\nDescribe workflow:\n\n"
    )

    result = classify_workflow(task)

    assigned_agent = route_agent(task)

    store_memory(task, result)

    store_agent_memory(
        assigned_agent,
        task
    )

    update_session_state(
        task,
        result
    )

    print(
        f"\nDetected Workflow: {result}"
    )

    print(
        f"\nAssigned Agent: {assigned_agent}"
    )


def contextual_search():

    query = input(
        "\nEnter contextual search query:\n\n"
    )

    ctx = RuntimeContext()

    knowledge_search = load_skill(
        "knowledge_search"
    )

    result = knowledge_search.execute(
        ctx,
        {
            "query": query
        }
    )

    matches = result.get("matches", [])

    print(
        "\n=== CONTEXTUAL MEMORY SEARCH ===\n"
    )

    if not matches:

        print(
            "No matching knowledge found in the vault."
        )

        return

    print(
        f"\nFound {len(matches)} matching knowledge files.\n"
    )

    for match in matches[:5]:

        print("\n" + "=" * 50)

        print(match["file"])

        print("=" * 50)

        print(match["snippet"])

        print("\n")


def create_objective():

    objective = input(
        "\nDescribe objective:\n\n"
    )

    add_objective(objective)


def create_operational_task():

    task = input(
        "\nDescribe task:\n\n"
    )

    create_task(task)

    assigned_agent = route_agent(task)

    store_agent_memory(
        assigned_agent,
        task
    )

    print(
        f"\nAssigned Agent: {assigned_agent}"
    )


def view_agent_memory_interface():

    agent = input(
        "\nEnter agent name:\n\n"
    )

    show_agent_memory(agent)


def execute_task_interface():

    task = input(
        "\nEnter execution task:\n\n"
    )

    execute_agent_task(task)


def plan_and_execute_interface():

    goal = input(
        "\nDescribe the goal to plan:\n\n"
    )

    # Single planning area, two engines:
    #   1. Sequential PlannerAgent (Phase 4) — flat plan, shared context, merged
    #      report. The default.
    #   2. Dependency-graph Planner — subtask DAG with topological ordering.
    print("\nPlanning mode:")
    print("  1. Sequential plan (PlannerAgent)  [default]")
    print("  2. Dependency graph (advanced)")

    mode = input("\nSelect mode [1]: ").strip() or "1"

    if mode == "2":

        outcome = Planner().run(goal)

        print("\n=== PLAN (dependency graph) ===\n")

        for step in outcome["steps"]:
            deps = step["depends_on"] or "-"
            print(f"  [{step['id']}] ({step['agent']}) {step['task']}  deps={deps}")

        print("\n=== FINAL ANSWER ===\n")

        print(outcome["final"])

        return

    # Sequential PlannerAgent (Phase 4).
    from agents.planner_agent import PlannerAgent

    def progress(index, total, agent, task):
        print(f"\n[step {index}/{total}] {agent}")
        print(f"   -> {task}")

    planner_agent = PlannerAgent()

    planner_agent.progress_callback = progress

    print("\n=== PLANNING & EXECUTING (sequential) ===")

    report = planner_agent.run(goal)

    print("\n=== FINAL COMBINED REPORT ===\n")

    print(report)


def ingest_document_interface():

    from core.document_store import DocumentStore

    path = input("\nPath to document:\n\n").strip().strip('"')

    try:
        info = DocumentStore().ingest(path)
        print(f"\nIngested {info['source']} -> {info['chunks']} chunks.")
    except Exception as error:
        print(f"\nCould not ingest: {error}")


def ask_documents_interface():

    from pathlib import Path
    from core.document_store import DocumentStore
    from core.llm_engine import query_llm

    question = input("\nAsk over your documents:\n\n")

    hits = DocumentStore().search(question, k=4)

    if not hits:
        print("\nNo relevant document content found.")
        return

    parts = []
    for h in hits:
        try:
            parts.append(Path(h["file"]).read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            parts.append(h.get("snippet", ""))

    context = "\n\n".join(parts)

    prompt = (
        "Answer the question using ONLY the context below. If the context is "
        "insufficient, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )

    print("\n=== ANSWER (RAG over documents) ===\n")
    # Documents are treated as private -> answered locally.
    print(query_llm(prompt, sensitive=True))


def view_escalations_interface():

    from core.escalation import list_escalations

    print("\n=== CLAUDE ESCALATION QUEUE ===\n")
    print(list_escalations() or "No escalations recorded yet.")


def run_eval_interface():

    from core.eval.harness import load_cases, run_eval, history
    from core.llm_engine import query_llm

    cases = load_cases()

    print("\n=== EVAL SUITE ===\n")

    if not cases:
        print("No eval cases found (src/core/eval/cases.jsonl).")
        return

    # The thing under test: a plain model call. Swap for an agent/plan to eval
    # those instead — the harness doesn't care.
    report = run_eval(cases, lambda task: query_llm(task), label="menu")

    print(report.render())

    prior = history(limit=6)
    if len(prior) > 1:
        print("\nRecent runs (pass_rate):")
        for row in prior:
            print(f"  {row['timestamp'][:19]}  {row['label']:<10} "
                  f"{row['pass_rate']:.0%}  (n={row['n']})")


def curate_vault_interface():

    from core.curator import scan_vault, apply_plan

    print("\n=== VAULT CURATION (dry run) ===\n")

    plan = scan_vault()

    print(plan.render())

    if not plan.to_delete:
        print("\nVault is clean — nothing to do.")
        return

    confirm = input(
        f"\nDelete {len(plan.to_delete)} note(s)? This is irreversible. [y/N] "
    ).strip().lower()

    if confirm == "y":
        deleted = apply_plan(plan)
        print(f"\nRemoved {len(deleted)} note(s).")
    else:
        print("\nNo changes made.")


def tool_agent_interface():

    from agents.tool_agent import ToolAgent
    from core.tools.builtin import (
        PythonTool, ReadFileTool, WriteFileTool, WebFetchTool,
    )
    from configs.paths import SRC

    # File tools are jailed to a dedicated work directory — they can't read or
    # write outside it.
    workroot = SRC / "state" / "toolspace"
    workroot.mkdir(parents=True, exist_ok=True)

    task = input("\nEnter a task for the tool-using agent:\n\n")

    # web_fetch is DANGEROUS (network egress) → default-denied. Granting it here
    # demonstrates the explicit-allow path of the permission policy.
    allow_net = input(
        "\nAllow network access (web_fetch)? [y/N] "
    ).strip().lower() == "y"

    tools = [
        PythonTool(),
        ReadFileTool(str(workroot)),
        WriteFileTool(str(workroot)),
    ]

    allow = []

    if allow_net:
        tools.append(WebFetchTool())
        allow = ["web_fetch"]

    agent = ToolAgent("tool-agent", "General Tool User")
    agent.tools = tools
    agent.allow = allow

    print(
        f"\nTools available: {', '.join(t.name for t in tools)} "
        f"(work dir: {workroot})"
    )

    agent.run(task)


def run_lift_benchmark_interface():
    from core.eval.lift_benchmark import run_benchmark
    print("\n=== ORCHESTRATION LIFT BENCHMARK ===\n")
    K_str = input("Number of trials per case [3]: ").strip()
    K = int(K_str) if K_str.isdigit() else 3
    print("\nExecuting benchmark (this will make real LLM calls)...")
    try:
        report = run_benchmark(K=K)
        print("\n=== BENCHMARK COMPLETED ===")
        print("\nCategory Results:")
        for cat in report["categories"]:
            earns = "✅ YES" if cat["earns_cost"] else "❌ NO"
            print(f"  {cat['category']:<20} | Score: {cat['pipeline_score_mean']:.2f} (pipeline) vs {cat['baseline_score_mean']:.2f} (baseline) | Lift: {cat['raw_lift']:.2f} | Cost-Adjusted Lift: {cat['cost_adjusted_lift']:.3f} | Earns Cost? {earns}")
    except Exception as error:
        print(f"\nBenchmark failed: {error}")


def vault_index_interface():

    # K-B: (re)index the real Obsidian vault into a local, read-only index.
    print("\n=== INDEX OBSIDIAN VAULT ===\n")
    try:
        from core.vault_store import VaultStore
        store = VaultStore()
        print(f"Indexing notes under: {store.vault}")
        print("(read-only; private; local embeddings)\n")
        stats = store.reindex()
        print(f"Indexed {stats.get('total', 0)} notes "
              f"(added {stats.get('added', 0)}, updated {stats.get('updated', 0)}, "
              f"removed {stats.get('removed', 0)}).")
        folders = store.folders()
        if folders:
            print("Folders: " + ", ".join(folders))
    except Exception as error:
        print(f"\nCould not index vault: {error}")


def vault_search_interface():

    # K-C MVP: ask the real vault, local-first. Always shows the extractive
    # answer (retrieval only, nothing leaves the device); optionally synthesizes
    # a LOCAL answer; only sends to the cloud after explicit, informed consent
    # (which is logged). Folder scope optional, e.g. "daily-ops".
    print("\n=== ASK OBSIDIAN NOTES (local-first; private) ===\n")
    try:
        from core.vault_qa import (
            retrieve, extractive_answer, local_synthesis, cloud_synthesis,
        )
        from core.consent import consent_count

        query = input("Ask / search your notes:\n\n").strip()
        if not query:
            return
        folder = input(
            "Limit to folder (blank = all, e.g. daily-ops):\n\n"
        ).strip() or None

        passages = retrieve(query, k=5, folder=folder)
        if not passages:
            print("\nNo matching notes found.")
            return

        print("\n--- Relevant notes (local; nothing left your device) ---\n")
        print(extractive_answer(passages))

        if input(
            "\nSynthesize an answer from these notes locally? [y/N]: "
        ).strip().lower() != "y":
            return

        print("\n(local model; private)\n")
        text, ok = local_synthesis(query, passages)
        if ok:
            print(text)
        else:
            print("[local model could not produce a reliable answer — "
                  "your notes above are the result]")

        # Cloud escalation: only on explicit, informed consent.
        want_more = (not ok) or input(
            "\nWant a stronger answer? [y/N]: "
        ).strip().lower() == "y"
        if not want_more:
            return

        srcs = [p.get("source") for p in passages[:4]]
        approx = sum(len(p.get("snippet") or "") for p in passages[:4]) + len(query)
        print("\n  WARNING: this SENDS your question and the following note "
              f"snippet(s) (~{approx} chars) to Ollama's cloud servers")
        print("  (this content LEAVES your device):")
        for s in srcs:
            print(f"    - {s}")
        if input("Proceed? [y/N]: ").strip().lower() != "y":
            print("Kept local. Nothing was sent.")
            return

        try:
            answer = cloud_synthesis(query, passages)
        except Exception as send_error:
            # Fail-closed: if consent could not be logged, nothing is sent.
            print(f"\nNot sent (consent could not be logged / call failed): {send_error}")
            return

        print("\n--- Cloud answer ---\n")
        print(answer)
        print(f"\n[logged to consent_log.jsonl — {consent_count()} total cloud send(s)]")
    except Exception as error:
        print(f"\nCould not answer: {error}")


def main():

    show_banner()

    # K-A: keep the knowledge vault clean automatically (prune error/empty notes
    # + collapse duplicates) so retrieval quality does not decay over time.
    # Best-effort, scoped to the agent-distillation vault; never blocks startup.
    try:
        from core.curator import auto_curate
        result = auto_curate()
        if result.get("deleted"):
            print(f"\n[curator] cleaned {result['deleted']} low-value/duplicate vault notes.")
    except Exception:
        pass

    while True:

        show_menu()

        choice = input(
            "\nSelect operation:\n\n"
        )

        if choice == "1":

            generate_context_package()

        elif choice == "2":

            generate_runtime_prompt()

        elif choice == "3":

            workflow_classification()

        elif choice == "4":

            run_diagnostics()

        elif choice == "5":

            recall_recent_memory()

        elif choice == "6":

            contextual_search()

        elif choice == "7":

            generate_insights()

        elif choice == "8":

            create_objective()

        elif choice == "9":

            show_objectives()

        elif choice == "10":

            create_operational_task()

        elif choice == "11":

            view_tasks()

        elif choice == "12":

            show_agent_status()

        elif choice == "13":

            view_agent_memory_interface()

        elif choice == "14":

            execute_task_interface()

        elif choice == "15":

            plan_and_execute_interface()

        elif choice == "16":

            ingest_document_interface()

        elif choice == "17":

            ask_documents_interface()

        elif choice == "18":

            view_escalations_interface()

        elif choice == "19":

            run_eval_interface()

        elif choice == "20":

            curate_vault_interface()

        elif choice == "21":

            tool_agent_interface()

        elif choice == "22":

            run_lift_benchmark_interface()

        elif choice == "23":

            vault_index_interface()

        elif choice == "24":

            vault_search_interface()

        elif choice == "25":

            print(
                "\nExiting system.\n"
            )

            break

        else:

            print(
                "\nInvalid selection."
            )


if __name__ == "__main__":

    main()