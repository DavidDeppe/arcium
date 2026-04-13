"""
arcium/review/reviewer.py

Core reviewer logic. Uses the Anthropic SDK to evaluate an architecture document
against a standards file and returns a structured ReviewReport.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load API key from the architecture-reviewer PoC's own .env, NOT Arcium's .env.
# Arcium's .env intentionally omits ANTHROPIC_API_KEY so its pipeline agents authenticate
# via Claude Code's Max plan subscription rather than direct API billing.
# This tool uses the SDK directly and requires a separate key.
_REVIEWER_ENV = Path.home() / "projects" / "architecture-reviewer" / ".env"
if _REVIEWER_ENV.exists():
    load_dotenv(dotenv_path=_REVIEWER_ENV, override=False)


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"

SYSTEM_PROMPT = """\
You are a senior enterprise architect conducting a formal architecture review.
Your role is to evaluate an architecture document against a set of established standards
and best practices, then produce a structured findings report.

Be specific and actionable. Reference concrete elements from the architecture document
(service names, configuration choices, missing components) rather than giving generic advice.
Weight findings by their actual risk impact to the system's reliability, security, and maintainability.
"""

USER_PROMPT_TEMPLATE = """\
Review the architecture document below against the provided standards.

<architecture>
{architecture}
</architecture>

<standards>
{standards}
</standards>

Produce your findings as a JSON object inside a ```json``` code fence. Use exactly this schema:

{{
  "compliance_score": <integer 0-100, where 100 = fully compliant with all standards>,
  "summary": "<2-3 sentence executive summary of the architecture's overall compliance posture>",
  "findings": [
    {{
      "severity": "<CRITICAL | HIGH | MEDIUM | LOW>",
      "area": "<short topic label, e.g. 'Observability', 'Scalability', 'Security'>",
      "gap": "<precise description of what is missing or non-compliant in this architecture>",
      "recommendation": "<specific, actionable fix with concrete technology or configuration guidance>"
    }}
  ]
}}

Severity guide:
- CRITICAL: A gap that directly threatens data integrity, availability, or security in production.
- HIGH: A significant architectural weakness that will cause reliability or maintainability problems.
- MEDIUM: A meaningful gap that should be addressed before scale increases or complexity grows.
- LOW: A best-practice improvement that would increase quality but has limited immediate risk.

Sort findings from CRITICAL down to LOW. Do not include any text outside the ```json``` block.
"""


@dataclass
class ReviewFinding:
    severity: str
    area: str
    gap: str
    recommendation: str


@dataclass
class ReviewReport:
    compliance_score: int
    summary: str
    findings: list[ReviewFinding]
    model: str
    input_tokens: int
    output_tokens: int

    @property
    def findings_by_severity(self) -> dict[str, list[ReviewFinding]]:
        buckets: dict[str, list[ReviewFinding]] = {
            "CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []
        }
        for f in self.findings:
            buckets.setdefault(f.severity, []).append(f)
        return buckets


class ArchitectureReviewer:
    """
    Reviews an architecture document against a standards file using the Anthropic SDK.

    Usage:
        reviewer = ArchitectureReviewer()
        report = reviewer.review(architecture_text, standards_text)
    """

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        # _REVIEWER_ENV is loaded at module level — do NOT call load_dotenv() here,
        # which would walk up to find Arcium's .env and potentially corrupt its config.
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set.\n"
                "Options:\n"
                "  1. export ANTHROPIC_API_KEY=sk-ant-... in your shell, then re-run\n"
                f"  2. Create {_REVIEWER_ENV} containing:\n"
                "        ANTHROPIC_API_KEY=sk-ant-...\n"
                "Note: Do NOT add this key to Arcium's .env — that file intentionally omits it\n"
                "so Arcium pipeline agents authenticate via Claude Code subscription billing."
            )

        # Import here to keep the module importable without anthropic installed
        import anthropic  # noqa: PLC0415
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self.model = model

    def review(self, architecture_text: str, standards_text: str) -> ReviewReport:
        """
        Run an architecture review and return a structured ReviewReport.

        Args:
            architecture_text: Full text of the architecture document.
            standards_text: Full text of the standards/best-practices document.

        Returns:
            ReviewReport with compliance score, summary, and severity-bucketed findings.
        """
        user_message = USER_PROMPT_TEMPLATE.format(
            architecture=architecture_text.strip(),
            standards=standards_text.strip(),
        )

        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        response_text = response.content[0].text
        return self._parse_response(
            response_text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    def _parse_response(
        self, text: str, input_tokens: int, output_tokens: int
    ) -> ReviewReport:
        # Extract JSON from a ```json ... ``` fence
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            json_text = match.group(1)
        else:
            # Fallback: try to parse the whole response as JSON
            json_text = text.strip()

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Model returned malformed JSON. Raw response:\n{text}"
            ) from exc

        findings = [
            ReviewFinding(
                severity=f.get("severity", "LOW").upper(),
                area=f.get("area", "General"),
                gap=f.get("gap", ""),
                recommendation=f.get("recommendation", ""),
            )
            for f in data.get("findings", [])
        ]

        # Ensure findings are sorted CRITICAL → LOW regardless of model output order
        findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 99))

        return ReviewReport(
            compliance_score=int(data.get("compliance_score", 0)),
            summary=data.get("summary", ""),
            findings=findings,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
