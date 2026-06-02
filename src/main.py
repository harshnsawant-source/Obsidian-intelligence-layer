from datetime import datetime

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

    print("15. Exit")


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


def main():

    show_banner()

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