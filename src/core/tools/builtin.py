# Built-in tools. Each declares only its risk tier; gating is the policy's job.
# See TOOL_FRAMEWORK.md section 5.

import os
import subprocess

from core.tools.base import Tool, ToolResult, Risk
from core.sandbox import run_python
from core.log import get_logger


log = get_logger("tools")

# Reuse the sandbox's output cap for tool observations too.
OUTPUT_LIMIT = 10000


def _clip(text):
    text = text or ""
    if len(text) > OUTPUT_LIMIT:
        return text[:OUTPUT_LIMIT] + "\n...[truncated]"
    return text


def _jailed(root, path):
    # Resolve `path` under `root` and reject anything that escapes it. The
    # file-system analogue of the sandbox's temp-dir confinement.
    root_real = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root_real, path))
    if target != root_real and not target.startswith(root_real + os.sep):
        return None
    return target


class PythonTool(Tool):

    name = "python"
    description = "Run a short Python 3 snippet and return its stdout/stderr."
    parameters = {"code": "the Python source to execute"}
    risk = Risk.MODERATE
    network = False

    def __init__(self, timeout=10):
        self.timeout = timeout

    def run(self, args):
        code = (args or {}).get("code", "")
        if not str(code).strip():
            return ToolResult(False, error="no code provided")
        res = run_python(str(code), timeout=self.timeout)
        if res.ok:
            return ToolResult(True, output=_clip(res.stdout) or "(no output)")
        return ToolResult(False, error=_clip(res.error_text))


class ReadFileTool(Tool):

    name = "read_file"
    description = "Read a UTF-8 text file within the allowed directory."
    parameters = {"path": "path relative to the tool root"}
    risk = Risk.SAFE
    network = False

    def __init__(self, root):
        self.root = root

    def run(self, args):
        path = (args or {}).get("path", "")
        target = _jailed(self.root, str(path))
        if target is None:
            return ToolResult(False, error="path escapes the allowed root")
        if not os.path.isfile(target):
            return ToolResult(False, error="file not found")
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as fh:
                return ToolResult(True, output=_clip(fh.read()))
        except Exception as error:
            return ToolResult(False, error=str(error))


class WriteFileTool(Tool):

    name = "write_file"
    description = "Write a UTF-8 text file within the allowed work directory."
    parameters = {"path": "path relative to the work root", "content": "text to write"}
    risk = Risk.MODERATE
    network = False

    def __init__(self, root):
        self.root = root

    def run(self, args):
        args = args or {}
        path = str(args.get("path", ""))
        content = args.get("content", "")
        target = _jailed(self.root, path)
        if target is None:
            return ToolResult(False, error="path escapes the allowed root")
        try:
            os.makedirs(os.path.dirname(target) or self.root, exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(str(content))
            return ToolResult(True, output=f"wrote {len(str(content))} chars to {path}")
        except Exception as error:
            return ToolResult(False, error=str(error))


class WebFetchTool(Tool):

    name = "web_fetch"
    description = "HTTP GET a URL and return the response body as text."
    parameters = {"url": "the http(s) URL to fetch"}
    risk = Risk.DANGEROUS   # network egress -> default-denied + blocked when sensitive
    network = True

    def __init__(self, timeout=15):
        self.timeout = timeout

    def run(self, args):
        url = str((args or {}).get("url", "")).strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return ToolResult(False, error="url must start with http:// or https://")
        try:
            import requests
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return ToolResult(True, output=_clip(resp.text))
        except Exception as error:
            return ToolResult(False, error=str(error))


class ShellTool(Tool):

    # Implemented to demonstrate the DANGEROUS tier and the default-deny gate.
    # NOT placed in the default registry — a shell can trivially egress.
    name = "shell"
    description = "Run a shell command and return its output."
    parameters = {"command": "the command line to run"}
    risk = Risk.DANGEROUS
    network = True   # a shell can curl/wget — treat as egress-capable for privacy

    def __init__(self, timeout=15):
        self.timeout = timeout

    def run(self, args):
        command = str((args or {}).get("command", "")).strip()
        if not command:
            return ToolResult(False, error="no command provided")
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=self.timeout,
            )
            out = _clip((proc.stdout or "") + (proc.stderr or ""))
            return ToolResult(proc.returncode == 0, output=out,
                              error="" if proc.returncode == 0 else out)
        except Exception as error:
            return ToolResult(False, error=str(error))
