"""
Data models for the WAT pipeline.
"""

from typing import Optional, List, Dict, Literal
from dataclasses import dataclass, field
import re
import yaml

from ..vault import VaultTools


@dataclass
class AgentContext:
    """Context passed between agents in the pipeline."""
    poc_slug: str
    scratch_dir: str              # 08-scratch/poc-pipeline-<slug>/
    project_dir: str              # ~/projects/<slug>/
    brief_path: str
    current_phase: str
    iteration_count: int
    specialist_outputs: Dict[str, str] = field(default_factory=dict)  # role → output path
    code_artifacts: Dict[str, str] = field(default_factory=dict)      # purpose → code path
    total_cost: float = 0.0
    failed: bool = False
    error: Optional[str] = None
    feedback_mode: bool = False
    feedback_text: Optional[str] = None


@dataclass
class IterationDecision:
    """Decision from Team Lead on how to proceed after Critic review."""
    action: Literal["proceed", "rework_architect", "rework_engineer", "escalate_human", "polish_engineer"]
    reason: str
    target_issues: List[str]  # Specific issues to address


@dataclass
class CriticIssue:
    """A single issue identified by the Critic."""
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    impact: str
    evidence: str
    recommended_fix: str
    responsible_agent: Literal["Architect", "Engineer", "Team Lead"]


@dataclass
class CriticAssessment:
    """
    Parsed output from Solutions Critic with structured frontmatter.
    """
    # From YAML frontmatter
    verdict: Literal["PASS", "PASS_WITH_CONDITIONS", "FAIL"]
    confidence: Literal["high", "medium", "low"]
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    root_cause: Optional[Literal["design_flaw", "implementation_bug", "infeasible"]]
    requires_human_decision: bool
    iteration_number: int

    # Parsed from markdown body
    issues: List[CriticIssue]
    summary: str
    strengths: List[str]

    # Acceptance test counts (from YAML frontmatter, optional for backwards compatibility)
    acceptance_tests_passed: int = 0
    acceptance_tests_failed: int = 0

    @classmethod
    def parse_from_report(cls, report_path: str, vault: VaultTools) -> "CriticAssessment":
        """
        Parse the critic's markdown report with YAML frontmatter.

        Args:
            report_path: Path to critic report in vault
            vault: VaultTools instance for reading

        Returns:
            Structured CriticAssessment

        Raises:
            ValueError: If frontmatter is missing or malformed
        """
        # Read the report
        content = vault.read_file(report_path)

        # Split frontmatter from body
        frontmatter, body = cls._split_frontmatter(content)

        # Parse YAML frontmatter
        metadata = yaml.safe_load(frontmatter)

        # Validate required fields
        required_fields = [
            'verdict', 'confidence', 'critical-count', 'high-count',
            'medium-count', 'low-count', 'iteration-number'
        ]
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"Missing required field in Critic frontmatter: {field}")

        # Parse issues from markdown body
        issues = cls._parse_issues_from_body(body)
        summary = cls._extract_summary(body)
        strengths = cls._extract_strengths(body)

        return cls(
            verdict=metadata['verdict'],
            confidence=metadata['confidence'],
            critical_count=metadata['critical-count'],
            high_count=metadata['high-count'],
            medium_count=metadata['medium-count'],
            low_count=metadata['low-count'],
            acceptance_tests_passed=metadata.get('acceptance-tests-passed', 0),
            acceptance_tests_failed=metadata.get('acceptance-tests-failed', 0),
            root_cause=metadata.get('root-cause'),
            requires_human_decision=metadata.get('requires-human-decision', False),
            iteration_number=metadata['iteration-number'],
            issues=issues,
            summary=summary,
            strengths=strengths
        )

    @staticmethod
    def _split_frontmatter(content: str) -> tuple[str, str]:
        """Split YAML frontmatter from markdown body."""
        pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            raise ValueError("No YAML frontmatter found in Critic report")

        return match.group(1), match.group(2)

    @staticmethod
    def _parse_issues_from_body(body: str) -> List[CriticIssue]:
        """Parse structured issues from markdown body."""
        issues = []

        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            section_pattern = rf'## {severity.title()} Issues\s*\n(.*?)(?=\n## |\Z)'
            section_match = re.search(section_pattern, body, re.DOTALL | re.IGNORECASE)

            if not section_match:
                continue

            section_content = section_match.group(1)

            # Parse individual issues
            issue_pattern = rf'### {severity}-(\d+): (.+?)\n(.*?)(?=\n### |\Z)'
            for issue_match in re.finditer(issue_pattern, section_content, re.DOTALL):
                title = issue_match.group(2).strip()
                issue_body = issue_match.group(3)

                # Extract structured fields
                impact = CriticAssessment._extract_field(issue_body, "Impact")
                evidence = CriticAssessment._extract_field(issue_body, "Evidence")
                recommended_fix = CriticAssessment._extract_field(issue_body, "Recommended fix")
                responsible_agent = CriticAssessment._extract_field(issue_body, "Responsible agent")

                issues.append(CriticIssue(
                    severity=severity.lower(),
                    title=title,
                    impact=impact or "Not specified",
                    evidence=evidence or "Not specified",
                    recommended_fix=recommended_fix or "Not specified",
                    responsible_agent=responsible_agent or "Team Lead"
                ))

        return issues

    @staticmethod
    def _extract_field(text: str, field_name: str) -> Optional[str]:
        """Extract a bold field value from markdown."""
        pattern = rf'\*\*{field_name}\*\*:\s*(.+?)(?=\n- \*\*|\n###|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_summary(body: str) -> str:
        """Extract overall assessment summary."""
        pattern = r'## Overall Assessment\s*\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, body, re.DOTALL)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_strengths(body: str) -> List[str]:
        """Extract list of strengths."""
        pattern = r'## Strengths\s*\n(.*?)(?=\n## |\Z)'
        match = re.search(pattern, body, re.DOTALL)

        if not match:
            return []

        strengths_text = match.group(1)
        strength_items = re.findall(r'[-*]\s+(.+)', strengths_text)
        return [s.strip() for s in strength_items]

    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return self.critical_count > 0

    def has_high_issues(self) -> bool:
        """Check if there are any high severity issues."""
        return self.high_count > 0

    def get_issues_by_severity(self, severity: str) -> List[CriticIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity.lower()]

    def should_escalate_to_human(self) -> bool:
        """
        Determine if human escalation is needed based on Critic's assessment.

        Returns True if:
        - requires_human_decision flag is set (substantial HIGH issues)
        - FAIL verdict with infeasible root cause

        FAIL with design_flaw → routes to Architect (no human escalation)
        FAIL with implementation_bug → routes to Engineer (no human escalation)
        """
        return self.requires_human_decision or (
            self.verdict == "FAIL" and self.root_cause == "infeasible"
        )
