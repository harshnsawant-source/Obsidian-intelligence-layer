def execute(

    ctx,
    input_data

):

    workflow = input_data.get(

        "workflow",

        []

    )

    results = []

    for step in workflow:

        results.append(

            f"Executed: {step}"

        )

    return {

        "workflow_results":

        results

    }
