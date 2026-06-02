KEYWORDS = {

    "retrieval": [
        "memory",
        "search",
        "retrieve",
        "context"
    ],

    "creation": [
        "build",
        "project",
        "website",
        "dashboard"
    ],

    "operations": [
        "workflow",
        "runtime",
        "execution",
        "system"
    ]
}


def classify_workflow(text):

    text = text.lower()

    scores = {}

    for category, words in KEYWORDS.items():

        score = 0

        for word in words:

            score += text.count(word)

        scores[category] = score

    return max(scores, key=scores.get)


if __name__ == "__main__":

    task = input(
        "\nDescribe workflow:\n\n"
    )

    result = classify_workflow(task)

    print(
        f"\nDetected Workflow: {result}"
    )