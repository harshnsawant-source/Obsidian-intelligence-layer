class ModelAdapter:

    @staticmethod
    def normalize_response(data):

        response = data.get(

            "response",

            ""

        ).strip()

        thinking = data.get(

            "thinking",

            ""

        ).strip()

        if response:

            return response

        if thinking:

            return (

                "[NO FINAL ANSWER GENERATED]\n\n"

                + thinking

            )

        return "No response generated."