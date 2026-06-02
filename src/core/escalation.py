from datetime import datetime

from configs.paths import ESCALATIONS
from core.log import get_logger


log = get_logger("escalation")


def record_escalation(prompt, score):

    # Surface a HIGH-complexity task for manual review in Claude Pro. Append to
    # a queue file the user can actually read (Menu) — not just a log line.
    try:
        ESCALATIONS.parent.mkdir(parents=True, exist_ok=True)
        with open(ESCALATIONS, "a", encoding="utf-8") as f:
            f.write(
                f"\n## {datetime.now().isoformat()}  (complexity {score:.2f})\n\n"
                f"{str(prompt)[:600]}\n"
            )
    except Exception as error:
        log.warning("could not record escalation: %s", error)


def list_escalations():
    if not ESCALATIONS.exists():
        return ""
    return ESCALATIONS.read_text(encoding="utf-8", errors="ignore")
