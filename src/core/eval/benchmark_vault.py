# Isolated benchmark vault.
#
# The lift benchmark runs the CANONICAL pipeline (PlannerAgent -> PlanExecutor),
# and every subtask result + the final report auto-distill into the knowledge
# vault, while query_agent also dumps each output via save_memory and reads prior
# notes back through build_context. Run against the real vault, a benchmark would
# (a) POLLUTE it with throwaway notes and (b) leak the user's personal notes into
# benchmark prompts, making runs non-deterministic and privacy-unsafe.
#
# isolated_vault() redirects all three sinks/sources to a throwaway directory for
# the duration of a run, then restores them. The production code path is exercised
# UNCHANGED — only the on-disk locations move:
#
#   1. distillation vault + state/memory  <- RuntimeContext (reads PROJECT_ROOT
#                                             at construction; built fresh per
#                                             distill call, so patching the module
#                                             global is sufficient)
#   2. agent output dumps                 <- memory_writer.MEMORIES_DIR
#   3. retrieval reads                    <- context_builder._index (a fresh index
#                                             over the empty isolated vault)

import contextlib
import shutil
from pathlib import Path

import capability.core.runtime_context as runtime_context
import core.context_builder as context_builder
import core.memory_writer as memory_writer
from core.memory_index import MemoryIndex
from configs.paths import RUNTIME


@contextlib.contextmanager
def isolated_vault(root=None, keep=False):
    """Context manager that points all vault/memory writes AND retrieval reads at
    a throwaway directory, so a benchmark cannot pollute (or read) the real vault.

    root: directory to use (default runtime/benchmark_vault). keep: if True, leave
    the directory on disk for inspection; otherwise it is deleted on exit.
    Yields the root Path.
    """
    if root is None:
        root = RUNTIME / "benchmark_vault"
    root = Path(root)

    vault = root / "knowledge" / "vault"
    memories = root / "memories"
    index_path = root / "index" / "vault_index.json"

    vault.mkdir(parents=True, exist_ok=True)
    memories.mkdir(parents=True, exist_ok=True)
    index_path.parent.mkdir(parents=True, exist_ok=True)

    saved = {
        "rc_root": runtime_context.PROJECT_ROOT,
        "mw_dir": memory_writer.MEMORIES_DIR,
        "ci_index": context_builder._index,
    }

    try:
        # 1. KnowledgeStore.base_path = PROJECT_ROOT/knowledge/vault and
        #    MemoryStore.base_path = PROJECT_ROOT/state/memory are both computed
        #    from this module global at __init__; RuntimeContext is constructed
        #    fresh on every distill, so the redirect takes effect immediately.
        runtime_context.PROJECT_ROOT = root
        # 2. save_memory() agent-output dumps.
        memory_writer.MEMORIES_DIR = memories
        # 3. build_context() retrieval — fresh index over the empty isolated
        #    vault so trials neither read the real vault nor reuse its index.
        context_builder._index = MemoryIndex(vault=vault, index_path=index_path)

        yield root
    finally:
        runtime_context.PROJECT_ROOT = saved["rc_root"]
        memory_writer.MEMORIES_DIR = saved["mw_dir"]
        context_builder._index = saved["ci_index"]
        if not keep:
            shutil.rmtree(root, ignore_errors=True)
