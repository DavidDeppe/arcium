"""
arcium/review/cli.py

Command-line interface for the architecture reviewer.

Usage:
    poetry run python -m arcium.review \\
        --architecture path/to/architecture.md \\
        --standards path/to/standards.md \\
        [--output report.txt] \\
        [--format text|json] \\
        [--model claude-sonnet-4-5-20250929]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .reviewer import ArchitectureReviewer, ReviewReport, DEFAULT_MODEL, SEVERITY_ORDER


# ── Formatting helpers ─────────────────────────────────────────────────────────

_SEVERITY_COLORS = {
    "CRITICAL": "\033[91m",  # bright red
    "HIGH":     "\033[93m",  # bright yellow
    "MEDIUM":   "\033[94m",  # bright blue
    "LOW":      "\033[92m",  # bright green
}
_RESET = "\033[0m"


def _supports_color(stream) -> bool:
    return hasattr(stream, "isatty") and stream.isatty()


def _colorize(text: str, color_code: str, use_color: bool) -> str:
    if use_color:
        return f"{color_code}{text}{_RESET}"
    return text


def format_text_report(report: ReviewReport, use_color: bool = True) -> str:
    lines: list[str] = []

    # Score banner
    score = report.compliance_score
    if score >= 80:
        score_color = _SEVERITY_COLORS["LOW"]
    elif score >= 60:
        score_color = _SEVERITY_COLORS["MEDIUM"]
    elif score >= 40:
        score_color = _SEVERITY_COLORS["HIGH"]
    else:
        score_color = _SEVERITY_COLORS["CRITICAL"]

    score_display = _colorize(f"{score} / 100", score_color, use_color)
    lines += [
        "╔══════════════════════════════════════════════════════════════╗",
        "║  ARCHITECTURE REVIEW REPORT                                 ║",
        f"║  Compliance Score: {score_display:<43}║",
        "╚══════════════════════════════════════════════════════════════╝",
        "",
        report.summary,
        "",
    ]

    buckets = report.findings_by_severity
    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        group = buckets.get(severity, [])
        count = len(group)
        label = _colorize(f"── {severity} ({count})", _SEVERITY_COLORS.get(severity, ""), use_color)
        lines.append(f"{label} {'─' * max(0, 60 - len(severity) - 6)}")
        if count == 0:
            lines.append("  None")
        else:
            prefix_map = {"CRITICAL": "C", "HIGH": "H", "MEDIUM": "M", "LOW": "L"}
            p = prefix_map[severity]
            for i, finding in enumerate(group, 1):
                lines += [
                    f"",
                    f"  [{p}{i}] Area: {finding.area}",
                    f"       Gap: {finding.gap}",
                    f"       Fix: {finding.recommendation}",
                ]
        lines.append("")

    total = len(report.findings)
    lines += [
        "─" * 64,
        f"Total findings: {total}  |  "
        f"Model: {report.model}  |  "
        f"Tokens: {report.input_tokens:,} in / {report.output_tokens:,} out",
    ]

    return "\n".join(lines)


def format_json_report(report: ReviewReport) -> str:
    data = {
        "compliance_score": report.compliance_score,
        "summary": report.summary,
        "model": report.model,
        "usage": {
            "input_tokens": report.input_tokens,
            "output_tokens": report.output_tokens,
        },
        "findings": [
            {
                "severity": f.severity,
                "area": f.area,
                "gap": f.gap,
                "recommendation": f.recommendation,
            }
            for f in report.findings
        ],
    }
    return json.dumps(data, indent=2)


# ── CLI entry point ────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m arcium.review",
        description=(
            "Review an architecture document against a standards file using Claude.\n"
            "Produces a structured findings report with severity-bucketed issues\n"
            "and an overall compliance score."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  poetry run python -m arcium.review \\\n"
            "      --architecture examples/sample_architecture/architecture.md \\\n"
            "      --standards examples/sample_architecture/standards.md\n\n"
            "  poetry run python -m arcium.review \\\n"
            "      -a architecture.md -s standards.md --format json --output report.json\n"
        ),
    )
    parser.add_argument(
        "--architecture", "-a",
        required=True,
        metavar="FILE",
        help="Path to the architecture document (markdown or plain text)",
    )
    parser.add_argument(
        "--standards", "-s",
        required=True,
        metavar="FILE",
        help="Path to the standards/best-practices file",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        default=None,
        help="Write the report to this file instead of stdout",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default, human-readable) or 'json'",
    )
    parser.add_argument(
        "--model", "-m",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Read input files
    arch_path = Path(args.architecture)
    standards_path = Path(args.standards)

    for path, label in ((arch_path, "architecture"), (standards_path, "standards")):
        if not path.exists():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            sys.exit(1)
        if not path.is_file():
            print(f"error: {label} path is not a file: {path}", file=sys.stderr)
            sys.exit(1)

    architecture_text = arch_path.read_text(encoding="utf-8")
    standards_text = standards_path.read_text(encoding="utf-8")

    if not architecture_text.strip():
        print("error: architecture file is empty", file=sys.stderr)
        sys.exit(1)
    if not standards_text.strip():
        print("error: standards file is empty", file=sys.stderr)
        sys.exit(1)

    # Run the review
    print("Running architecture review…", file=sys.stderr)
    try:
        reviewer = ArchitectureReviewer(model=args.model)
        report = reviewer.review(architecture_text, standards_text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"error: review failed — {exc}", file=sys.stderr)
        sys.exit(1)

    # Format output
    use_color = args.format == "text" and args.output is None and _supports_color(sys.stdout)
    if args.format == "json":
        output = format_json_report(report)
    else:
        output = format_text_report(report, use_color=use_color)

    # Write output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"Report written to: {out_path}", file=sys.stderr)
    else:
        print(output)
