# Bounded execution of generated Python. This is BOUNDED, not ISOLATED — see
# VERIFICATION.md section 4. It runs code in a throwaway subprocess with a hard
# timeout and a temp working directory, std-lib only. It does NOT block the
# network; for untrusted code wrap this in an OS-level sandbox (container /
# firejail / Windows Sandbox).

import os
import sys
import shutil
import tempfile
import subprocess

from core.log import get_logger


log = get_logger("sandbox")

# Cap captured output so a runaway print can't exhaust memory / the context.
OUTPUT_LIMIT = 10000

# resource limits are Unix-only; on Windows we rely on the timeout alone.
try:
    import resource  # noqa: F401
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False


class ExecResult:

    def __init__(self, ok, returncode, stdout, stderr, timed_out):
        self.ok = ok
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    @property
    def error_text(self):
        # The concrete feedback a verifier feeds back into regeneration.
        if self.timed_out:
            return "Execution timed out."
        parts = []
        if self.stderr.strip():
            parts.append(self.stderr.strip())
        if self.returncode not in (0, None):
            parts.append(f"Process exited with code {self.returncode}.")
        return "\n".join(parts) or "Execution failed."

    def __repr__(self):
        return (
            f"ExecResult(ok={self.ok}, returncode={self.returncode}, "
            f"timed_out={self.timed_out})"
        )


def _limits(cpu_seconds, mem_bytes):
    # Best-effort Unix resource caps applied in the child before exec.
    def _apply():
        import resource as r
        r.setrlimit(r.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if mem_bytes:
            r.setrlimit(r.RLIMIT_AS, (mem_bytes, mem_bytes))
    return _apply


def run_python(code, timeout=10, mem_mb=256):

    # Run `code` (a string) in an isolated subprocess. Returns an ExecResult.
    # Never raises for ordinary failures (non-zero exit, exception, timeout) —
    # those are reported on the result so callers/verifiers can act on them.

    workdir = tempfile.mkdtemp(prefix="oil_sandbox_")

    script = os.path.join(workdir, "snippet.py")

    try:
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(code)

        # -I: isolated mode (ignore env vars + user site) so the child can't
        # inherit ambient config/credentials. cwd is the throwaway dir.
        kwargs = {
            "cwd": workdir,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
        }

        if _HAS_RESOURCE:
            kwargs["preexec_fn"] = _limits(timeout, mem_mb * 1024 * 1024)

        try:
            proc = subprocess.run(
                [sys.executable, "-I", script],
                **kwargs,
            )
        except subprocess.TimeoutExpired as expired:
            log.debug("sandbox timed out after %ss", timeout)
            return ExecResult(
                ok=False,
                returncode=None,
                stdout=_clip(expired.stdout),
                stderr=_clip(expired.stderr),
                timed_out=True,
            )

        return ExecResult(
            ok=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=_clip(proc.stdout),
            stderr=_clip(proc.stderr),
            timed_out=False,
        )

    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _clip(text):
    if not text:
        return ""
    if len(text) > OUTPUT_LIMIT:
        return text[:OUTPUT_LIMIT] + "\n...[output truncated]"
    return text
