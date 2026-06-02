from pathlib import Path
from datetime import datetime
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MemoryStore:

    def __init__(self):

        self.base_path = (
            PROJECT_ROOT /
            "state" /
            "memory"
        )

        self.root = self.base_path

    def write(

        self,
        store,
        filename,
        content

    ):

        target = (
            self.base_path /
            store
        )

        target.mkdir(
            parents=True,
            exist_ok=True
        )

        file_path = (
            target /
            filename
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(content)

        return str(file_path)

    def read(

        self,
        store,
        filename

    ):

        file_path = (
            self.base_path /
            store /
            filename
        )

        if not file_path.exists():

            return None

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()


class KnowledgeStore:

    def __init__(self):

        self.base_path = (
            PROJECT_ROOT /
            "knowledge" /
            "vault"
        )

        self.base_path.mkdir(
            parents=True,
            exist_ok=True
        )

    def write(

        self,
        filename,
        content

    ):

        file_path = (
            self.base_path /
            filename
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            file.write(content)

        return str(file_path)

    def read(

        self,
        filename

    ):

        file_path = (
            self.base_path /
            filename
        )

        if not file_path.exists():

            return None

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()


class TraceStore:

    def __init__(self):

        self.base_path = (
            PROJECT_ROOT /
            "state" /
            "traces"
        )

        self.base_path.mkdir(
            parents=True,
            exist_ok=True
        )

    def log(

        self,
        agent,
        task,
        response

    ):

        timestamp = datetime.now().isoformat()

        trace = {

            "timestamp": timestamp,
            "agent": agent,
            "task": task,
            "response": response

        }

        filename = (
            timestamp
            .replace(":", "-")
            + ".json"
        )

        file_path = (
            self.base_path /
            filename
        )

        with open(
            file_path,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                trace,
                file,
                indent=4
            )

        return str(file_path)


class RuntimeContext:

    def __init__(self):

        self.memory = MemoryStore()

        self.knowledge = KnowledgeStore()

        self.trace = TraceStore()