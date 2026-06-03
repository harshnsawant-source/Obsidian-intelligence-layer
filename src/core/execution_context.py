# Shared reasoning context threaded through a planned execution.
#
# The PlanExecutor owns one instance and is the ONLY component that mutates it,
# via the explicit record_output / add_* APIs below — never via direct list
# .append (Phase 5 hardening #2: a single write path makes future schema
# migrations + indexing a one-place change).
#
# Storage keeps FULL fidelity; BOUNDING happens only at render time
# (render_summary / distillation_digest), so nothing is ever lost from the
# object itself. render_full() is unbounded; render_summary() is deterministic,
# ranked, and budget-capped to prevent prompt explosion (hardening #1).
#
# All records are typed, id'd, JSON-serializable dicts (to_dict/from_dict) so a
# future Phase 6 retrieval layer can index findings/decisions/artifacts/etc.
# without redesigning this class (hardening #8).

import re
from datetime import datetime


# --- render/summary bounds (deterministic; prevent prompt explosion, #1) ---
SUMMARY_MAX_ITEMS = 5           # per structured section
RECENT_OUTPUTS = 3              # raw outputs are the biggest sink -> hard cap
SNIPPET_CHARS = 300             # per finding/decision/risk/assumption line
ARTIFACT_SNIPPET_CHARS = 400    # per artifact content in summary
OUTPUT_SNIPPET_CHARS = 600      # per forwarded raw output in summary
SUMMARY_MAX_CHARS = 6000        # final hard ceiling (~1.5k tokens)

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}


def _norm(text):
    return " ".join(str(text or "").split()).lower()


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")
    return s or "artifact"


def _clip(text, limit):
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + " ...[truncated]"


def _coerce_conf(value):
    if value is None:
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


class SharedExecutionContext:

    def __init__(self, goal):

        self.goal = goal

        # --- populated, full fidelity ---
        self.outputs = []          # [{agent, task, output}]
        self.completed_steps = []  # [{task, agent}]
        self.findings = []         # [finding record]
        self.decisions = []        # [decision record]
        self.artifacts = {}        # {logical_id: [version records]}  (#4)
        self.risks = []            # [risk record]  (#6 optional link)
        self.assumptions = []      # [assumption record]

        # --- internal: deterministic ids + dedup index ---
        self._counters = {"finding": 0, "decision": 0, "risk": 0, "assumption": 0}
        self._finding_keys = {}    # norm(finding text) -> finding id  (#3)

    # ---- ids / time -------------------------------------------------

    def _next_id(self, kind):
        self._counters[kind] += 1
        return f"{kind[0]}{self._counters[kind]}"

    @staticmethod
    def _now():
        return datetime.now().isoformat()

    # ---- mutation APIs (THE single write path; hardening #2) --------

    def record_output(self, agent, task, output):

        self.outputs.append({"agent": agent, "task": task, "output": output})
        self.completed_steps.append({"task": task, "agent": agent})

    def add_finding(self, finding, source="", confidence=None, agent=None):

        text = str(finding or "").strip()

        if not text:
            return None

        conf = _coerce_conf(confidence)
        key = _norm(text)

        # Exact-duplicate protection + merge (#3): structure leaves room for a
        # future semantic-dedup layer to hook in here (cluster by norm_key /
        # embedding) without changing callers.
        existing_id = self._finding_keys.get(key)

        if existing_id is not None:
            for rec in self.findings:
                if rec["id"] == existing_id:
                    rec["support_count"] += 1
                    if conf is not None:
                        rec["confidence"] = max(rec.get("confidence") or 0.0, conf)
                    if source and source not in rec["sources"]:
                        rec["sources"].append(source)
                    return existing_id

        fid = self._next_id("finding")
        self.findings.append({
            "id": fid,
            "finding": text,
            "sources": [source] if source else [],
            "confidence": conf,
            "support_count": 1,
            "agent": agent,
            "ts": self._now(),
            "norm_key": key,
        })
        self._finding_keys[key] = fid
        return fid

    def add_decision(self, decision, reasoning="", tradeoffs=None, agent=None):

        text = str(decision or "").strip()

        if not text:
            return None

        did = self._next_id("decision")
        self.decisions.append({
            "id": did,
            "decision": text,
            "reasoning": str(reasoning or ""),
            "tradeoffs": list(tradeoffs or []),
            "agent": agent,            # provenance (#5)
            "ts": self._now(),
        })
        return did

    def add_artifact(self, type, content, metadata=None, agent=None, id=None):

        # Versioned identity (#4): each logical id keeps an ascending list of
        # versions. latest = [-1]; old versions coexist for reference.
        logical_id = _slug(id or type)

        versions = self.artifacts.setdefault(logical_id, [])

        version = len(versions) + 1

        record = {
            "id": logical_id,
            "type": str(type or "artifact"),
            "content": content if content is not None else "",
            "metadata": dict(metadata or {}),
            "version": version,
            "agent": agent,
            "ts": self._now(),
        }

        versions.append(record)
        return logical_id, version

    def add_risk(self, risk, severity="medium", mitigation="",
                 agent=None, assumption_id=None):

        text = str(risk or "").strip()

        if not text:
            return None

        sev = str(severity or "medium").lower()
        if sev not in _SEVERITY_RANK:
            sev = "medium"

        rid = self._next_id("risk")
        self.risks.append({
            "id": rid,
            "risk": text,
            "severity": sev,
            "mitigation": str(mitigation or ""),
            "assumption_id": assumption_id,   # optional soft-link (#6)
            "agent": agent,
            "ts": self._now(),
        })
        return rid

    def add_assumption(self, assumption, confidence=None, agent=None):

        text = str(assumption or "").strip()

        if not text:
            return None

        aid = self._next_id("assumption")
        self.assumptions.append({
            "id": aid,
            "assumption": text,
            "confidence": _coerce_conf(confidence),
            "agent": agent,
            "ts": self._now(),
        })
        return aid

    def merge_contributions(self, contribs, agent=None):

        # Route a parsed contribution dict through the typed APIs, stamping the
        # ORIGINATING agent (authoritative — supplied by the executor, not
        # self-reported by the model). Malformed entries were dropped upstream.
        if not isinstance(contribs, dict):
            return

        for f in contribs.get("findings", []) or []:
            self.add_finding(f.get("finding"), f.get("source", ""),
                             f.get("confidence"), agent=agent)

        for d in contribs.get("decisions", []) or []:
            self.add_decision(d.get("decision"), d.get("reasoning", ""),
                              d.get("tradeoffs"), agent=agent)

        for a in contribs.get("artifacts", []) or []:
            self.add_artifact(a.get("type"), a.get("content"),
                              a.get("metadata"), agent=agent, id=a.get("id"))

        for r in contribs.get("risks", []) or []:
            self.add_risk(r.get("risk"), r.get("severity", "medium"),
                          r.get("mitigation", ""), agent=agent,
                          assumption_id=r.get("assumption_id"))

        for a in contribs.get("assumptions", []) or []:
            self.add_assumption(a.get("assumption"), a.get("confidence"),
                                agent=agent)

    # ---- helpers ----------------------------------------------------

    def latest_artifact(self, logical_id):
        versions = self.artifacts.get(_slug(logical_id))
        return versions[-1] if versions else None

    def artifact_versions(self, logical_id):
        return list(self.artifacts.get(_slug(logical_id), []))

    def assumption_for_risk(self, risk_record):
        aid = (risk_record or {}).get("assumption_id")
        if not aid:
            return None
        for a in self.assumptions:
            if a["id"] == aid:
                return a
        return None

    # ---- deterministic ranking (stable sort -> ties keep insert order) ----

    def _ranked_findings(self):
        return sorted(self.findings,
                      key=lambda f: (-(f.get("confidence") or 0.0),
                                     -f.get("support_count", 1)))

    def _ranked_risks(self):
        return sorted(self.risks,
                      key=lambda r: -_SEVERITY_RANK.get(r.get("severity"), 2))

    def _ranked_assumptions(self):
        return sorted(self.assumptions,
                      key=lambda a: -(a.get("confidence") or 0.0))

    # ---- rendering --------------------------------------------------

    def render_full(self):
        # Unbounded structured view (debugging / small contexts).
        return self._render(items=None, recent_outputs=None, hard_cap=None)

    def render_summary(self, max_items=SUMMARY_MAX_ITEMS, max_chars=SUMMARY_MAX_CHARS):
        # Bounded, deterministic, ranked — what PlanExecutor forwards (#1).
        return self._render(items=max_items, recent_outputs=RECENT_OUTPUTS,
                            hard_cap=max_chars)

    def render(self):
        # Backward-compatible alias (Phase 4 callers + tests use .render()).
        return self.render_summary()

    def _render(self, items, recent_outputs, hard_cap):

        sections = []

        non_empty = any([self.decisions, self.findings, self.artifacts,
                         self.risks, self.assumptions, self.outputs])

        if non_empty:
            sections.append(f"Goal: {self.goal}")

        # Decisions (recency-ordered; reasoning matters most going forward).
        dec = self.decisions[-items:] if items else self.decisions
        if dec:
            lines = []
            for d in dec:
                line = f"[{d['id']}] {_clip(d['decision'], SNIPPET_CHARS)}"
                if d.get("agent"):
                    line += f" (by {d['agent']})"
                if d.get("reasoning"):
                    line += f" - reasoning: {_clip(d['reasoning'], SNIPPET_CHARS)}"
                lines.append(line)
            sections.append("Decisions:\n" + "\n".join(lines))

        # Findings (confidence/support-ranked).
        finds = self._ranked_findings()
        finds = finds[:items] if items else finds
        if finds:
            lines = [
                f"[{f['id']}] {_clip(f['finding'], SNIPPET_CHARS)} "
                f"(confidence={f.get('confidence')}, support={f.get('support_count', 1)})"
                for f in finds
            ]
            sections.append("Findings:\n" + "\n".join(lines))

        # Artifacts (latest version of each logical id).
        if self.artifacts:
            lines = []
            for lid in sorted(self.artifacts):
                latest = self.artifacts[lid][-1]
                lines.append(
                    f"[{lid} v{latest['version']}] type={latest['type']}: "
                    f"{_clip(latest['content'], ARTIFACT_SNIPPET_CHARS)}"
                )
            sections.append("Artifacts (latest):\n" + "\n".join(lines))

        # Risks (severity-ranked; show optional assumption link).
        risks = self._ranked_risks()
        risks = risks[:items] if items else risks
        if risks:
            lines = []
            for r in risks:
                line = f"[{r['id']}] ({r['severity']}) {_clip(r['risk'], SNIPPET_CHARS)}"
                if r.get("mitigation"):
                    line += f" - mitigation: {_clip(r['mitigation'], SNIPPET_CHARS)}"
                if r.get("assumption_id"):
                    line += f" [from {r['assumption_id']}]"
                lines.append(line)
            sections.append("Risks:\n" + "\n".join(lines))

        # Assumptions (confidence-ranked).
        assums = self._ranked_assumptions()
        assums = assums[:items] if items else assums
        if assums:
            lines = [
                f"[{a['id']}] {_clip(a['assumption'], SNIPPET_CHARS)} "
                f"(confidence={a.get('confidence')})"
                for a in assums
            ]
            sections.append("Assumptions:\n" + "\n".join(lines))

        # Raw outputs LAST (biggest sink; trimmed first under budget).
        outs = self.outputs[-recent_outputs:] if recent_outputs else self.outputs
        if outs:
            lines = []
            for o in outs:
                body = _clip(o["output"], OUTPUT_SNIPPET_CHARS) if recent_outputs else o["output"]
                lines.append(f"[{o['agent']}] {o['task']}\n{body}")
            sections.append("Results so far:\n" + "\n\n".join(lines))

        text = "\n\n".join(sections)

        if hard_cap and len(text) > hard_cap:
            text = text[:hard_cap] + "\n...[context truncated to budget]"

        return text

    # ---- distillation digest (hardening #7) -------------------------

    def distillation_digest(self, max_items=SUMMARY_MAX_ITEMS):

        # Compact, bounded view for the vault: ONLY key reasoning. Excludes raw
        # outputs, low-confidence findings, old artifact versions, low-severity
        # risks, and assumptions (all transient) — keeps notes small + retrieval
        # signal high.
        parts = []

        finds = [f for f in self._ranked_findings()
                 if (f.get("confidence") or 0) >= 0.5][:max_items]
        if finds:
            parts.append("Key findings:\n" + "\n".join(
                f"- {_clip(f['finding'], SNIPPET_CHARS)} (confidence={f.get('confidence')})"
                for f in finds))

        if self.decisions:
            parts.append("Key decisions:\n" + "\n".join(
                f"- {_clip(d['decision'], SNIPPET_CHARS)}"
                for d in self.decisions[:max_items]))

        if self.artifacts:
            parts.append("Key artifacts:\n" + "\n".join(
                f"- {lid} v{self.artifacts[lid][-1]['version']} "
                f"(type={self.artifacts[lid][-1]['type']})"
                for lid in sorted(self.artifacts)))

        major = [r for r in self.risks if r.get("severity") == "high"][:max_items]
        if major:
            parts.append("Major risks:\n" + "\n".join(
                f"- {_clip(r['risk'], SNIPPET_CHARS)}"
                + (f" - mitigation: {_clip(r['mitigation'], SNIPPET_CHARS)}"
                   if r.get("mitigation") else "")
                for r in major))

        return "\n\n".join(parts)

    # ---- serialization (Phase 6 seam, hardening #8) -----------------

    def to_dict(self):
        return {
            "goal": self.goal,
            "outputs": self.outputs,
            "completed_steps": self.completed_steps,
            "findings": self.findings,
            "decisions": self.decisions,
            "artifacts": self.artifacts,
            "risks": self.risks,
            "assumptions": self.assumptions,
            "_counters": self._counters,
            "_finding_keys": self._finding_keys,
        }

    @classmethod
    def from_dict(cls, data):
        ctx = cls(data.get("goal", ""))
        ctx.outputs = list(data.get("outputs", []))
        ctx.completed_steps = list(data.get("completed_steps", []))
        ctx.findings = list(data.get("findings", []))
        ctx.decisions = list(data.get("decisions", []))
        ctx.artifacts = dict(data.get("artifacts", {}))
        ctx.risks = list(data.get("risks", []))
        ctx.assumptions = list(data.get("assumptions", []))
        ctx._counters = dict(data.get("_counters", ctx._counters))
        ctx._finding_keys = dict(data.get("_finding_keys", {}))
        return ctx
