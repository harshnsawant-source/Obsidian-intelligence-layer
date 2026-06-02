class SkillRouter:

    def route(

        self,
        task

    ):

        task = task.lower()

        if any(

            word in task

            for word in [

                "remember",
                "save",
                "store",
                "write"

            ]

        ):

            return [

                "memory_write"

            ]

        if any(

            word in task

            for word in [

                "recall",
                "find",
                "search"

            ]

        ):

            return [

                "memory_recall"

            ]

        return [

            "memory_recall",
            "context_build",
            "knowledge_distill"

        ]