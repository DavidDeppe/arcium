"""
arcium.review — Architecture review tool using the Anthropic SDK.

Evaluates an architecture document against a standards file and produces
a structured findings report with severity-bucketed issues and a compliance score.

Usage (CLI):
    poetry run python -m arcium.review \\
        --architecture path/to/architecture.md \\
        --standards path/to/standards.md

Usage (library):
    from arcium.review import ArchitectureReviewer

    reviewer = ArchitectureReviewer()
    report = reviewer.review(architecture_text, standards_text)
    print(report.compliance_score)
    for finding in report.findings:
        print(finding.severity, finding.area, finding.recommendation)
"""

from .reviewer import ArchitectureReviewer, ReviewReport, ReviewFinding

__all__ = ["ArchitectureReviewer", "ReviewReport", "ReviewFinding"]
