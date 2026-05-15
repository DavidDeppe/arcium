"""
MarketplaceValidator — validates CAST artifacts before marketplace publishing.

Phase 5a validation gates:
  1. Schema validation — required fields present, correct types
  2. Reference validation — all referenced agents/skills/tools exist
  3. Graph validation — all declared edges reference valid node IDs
  4. Test run verification — cohort has at least one successful run

Produces a validation-report.md alongside the cohort manifest.
Future: will be superseded by quality-gate-cohort for deeper evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from ..workflow.cohort_resolver import CohortManifestResolver, CohortManifest
from ..workflow.tool_resolver import ToolManifestResolver


@dataclass
class ValidationResult:
    cohort_id: str
    cohort_version: str
    status: str                      # 'passed' | 'failed' | 'warning'
    schema_valid: bool
    references_valid: bool
    graph_valid: bool
    test_run_verified: bool
    findings: list[str] = field(default_factory=list)
    reference_details: list[dict] = field(default_factory=list)
    test_run_details: dict = field(default_factory=dict)
    validated_at: str = ""


class MarketplaceValidator:
    """Validates CAST cohort artifacts for marketplace publishing readiness."""

    SCHEMA_REQUIRED = ["id", "version", "kind", "description", "agents",
                       "coordination", "sla", "quality_gates", "provenance"]

    def __init__(self, vault_path: Union[str, Path]):
        self.vault_path = Path(vault_path)
        self._resolver = CohortManifestResolver(vault_path)
        self._tool_resolver = ToolManifestResolver(vault_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, cohort_id: str) -> ValidationResult:
        """
        Run all four validation gates for a cohort.

        Returns ValidationResult with status 'passed', 'failed', or 'warning'.
        """
        manifest = self._resolver.load_manifest(cohort_id)
        raw_fm = self._load_raw_frontmatter(cohort_id)

        findings: list[str] = []
        reference_details: list[dict] = []

        schema_valid, schema_findings = self._validate_schema(raw_fm)
        findings.extend(schema_findings)

        refs_valid, ref_details, ref_findings = self._validate_references(manifest)
        reference_details.extend(ref_details)
        findings.extend(ref_findings)

        graph_valid, graph_findings = self._validate_graph(manifest)
        findings.extend(graph_findings)

        run_verified, run_details, run_findings = self._verify_test_run(cohort_id)
        findings.extend(run_findings)

        if not schema_valid or not refs_valid or not graph_valid:
            status = "failed"
        elif not run_verified:
            status = "warning"
        else:
            status = "passed"

        return ValidationResult(
            cohort_id=cohort_id,
            cohort_version=manifest.version,
            status=status,
            schema_valid=schema_valid,
            references_valid=refs_valid,
            graph_valid=graph_valid,
            test_run_verified=run_verified,
            findings=findings,
            reference_details=reference_details,
            test_run_details=run_details,
            validated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def write_report(self, result: ValidationResult, cohort_dir: Path) -> Path:
        """Write <cohort-id>-validation.md to cohort_dir. Returns the path."""
        report_path = cohort_dir / f"{result.cohort_id}-validation.md"
        report_path.write_text(self._render_report(result), encoding="utf-8")
        return report_path

    # ------------------------------------------------------------------
    # Gate 1: Schema validation
    # ------------------------------------------------------------------

    def _validate_schema(self, fm: dict) -> tuple[bool, list[str]]:
        findings = []

        missing = [f for f in self.SCHEMA_REQUIRED if f not in fm]
        if missing:
            findings.append(f"Missing required fields: {missing}")

        if fm.get("kind") != "cohort":
            findings.append(f"kind must be 'cohort', got '{fm.get('kind')}'")

        coord = fm.get("coordination", {})
        if not isinstance(coord, dict) or "max_iterations" not in coord:
            findings.append("coordination.max_iterations is required")
        elif not isinstance(coord["max_iterations"], int) or coord["max_iterations"] <= 0:
            findings.append("coordination.max_iterations must be a positive integer")

        sla = fm.get("sla", {})
        if not isinstance(sla, dict) or "max_total_cost_usd" not in sla:
            findings.append("sla.max_total_cost_usd is required")
        else:
            try:
                if float(sla["max_total_cost_usd"]) <= 0:
                    findings.append("sla.max_total_cost_usd must be > 0")
            except (TypeError, ValueError):
                findings.append("sla.max_total_cost_usd must be a number")

        return len(findings) == 0, findings

    # ------------------------------------------------------------------
    # Gate 2: Reference validation
    # ------------------------------------------------------------------

    def _validate_references(self, manifest: CohortManifest) -> tuple[bool, list[dict], list[str]]:
        details = []
        findings = []

        bundles = self._tool_resolver._load_bundles()

        for role_spec in manifest.agents:
            # Agent reference
            agent_found = role_spec.agent_id in self._resolver._agent_index
            details.append({
                "id": role_spec.agent_id,
                "kind": "agent",
                "status": "found" if agent_found else "missing",
            })
            if not agent_found:
                findings.append(f"Agent '{role_spec.agent_id}' not found in marketplace")

            # Skill references
            for skill_id in role_spec.skills_add:
                skill_found = skill_id in self._resolver._skill_index
                details.append({
                    "id": skill_id,
                    "kind": "skill",
                    "status": "found" if skill_found else "missing",
                })
                if not skill_found:
                    findings.append(f"Skill '{skill_id}' not found in marketplace")

            # Tool bundle reference
            bundle_name = role_spec.tools
            bundle_found = bundle_name in bundles
            details.append({
                "id": bundle_name,
                "kind": "tool-bundle",
                "status": "found" if bundle_found else "missing",
            })
            if not bundle_found:
                findings.append(f"Tool bundle '{bundle_name}' not found in _bundles.yaml")

        all_found = all(d["status"] == "found" for d in details)
        return all_found, details, findings

    # ------------------------------------------------------------------
    # Gate 3: Graph validation
    # ------------------------------------------------------------------

    def _validate_graph(self, manifest: CohortManifest) -> tuple[bool, list[str]]:
        findings = []

        coord = manifest.coordination
        if coord.get("runtime_routing") != "enabled":
            return True, []

        if not manifest.graph_nodes:
            findings.append("runtime_routing is 'enabled' but no graph nodes are declared")
            return False, findings

        valid_ids = set(manifest.graph_nodes.keys())
        role_ids = {s.role for s in manifest.agents}

        for node_id, node in manifest.graph_nodes.items():
            if node.role not in role_ids:
                findings.append(
                    f"Graph node '{node_id}' references role '{node.role}' "
                    f"which is not declared in agents"
                )

            if node.default_next is not None and node.default_next not in valid_ids:
                findings.append(
                    f"Graph node '{node_id}' default_next='{node.default_next}' "
                    f"is not a valid node ID"
                )

            for route in node.valid_routes:
                if route not in valid_ids:
                    findings.append(
                        f"Graph node '{node_id}' valid_routes contains '{route}' "
                        f"which is not a valid node ID"
                    )

        terminal_nodes = [n for n in manifest.graph_nodes.values() if n.terminal]
        if not terminal_nodes:
            findings.append("Graph has no terminal node (terminal: true)")

        return len(findings) == 0, findings

    # ------------------------------------------------------------------
    # Gate 4: Test run verification
    # ------------------------------------------------------------------

    def _verify_test_run(self, cohort_id: str) -> tuple[bool, dict, list[str]]:
        decisions_path = self.vault_path / "00-index" / "COHORT-DECISIONS.md"
        if not decisions_path.exists():
            return False, {}, ["COHORT-DECISIONS.md not found — cannot verify test runs"]

        content = decisions_path.read_text(encoding="utf-8")

        # Header pattern: ## [DATE] slug · run-id: X · cohort: <id> v<version>
        # Outcome pattern: **Outcome:** completed · ...
        # Parse by splitting on section headers and scanning each block.
        current_entry: dict | None = None
        completed_runs: list[dict] = []

        for line in content.splitlines():
            header_match = re.match(
                r"^## \[(\d{4}-\d{2}-\d{2})[^\]]*\]\s+\S+\s+·\s+run-id:\s+(\S+)\s+·\s+cohort:\s+(\S+)\s+v(\S+)",
                line,
            )
            if header_match:
                current_entry = {
                    "date": header_match.group(1),
                    "run_id": header_match.group(2),
                    "cohort_id": header_match.group(3),
                    "version": header_match.group(4),
                }
                continue

            if current_entry and current_entry["cohort_id"] == cohort_id:
                outcome_match = re.match(
                    r"^\*\*Outcome:\*\*\s+(\w+)\s*·\s*\*\*Iterations:\*\*\s*(\d+)\s*·\s*\*\*Cost:\*\*\s*(\S+)",
                    line,
                )
                if outcome_match:
                    current_entry["outcome"] = outcome_match.group(1)
                    current_entry["iterations"] = int(outcome_match.group(2))
                    current_entry["cost"] = outcome_match.group(3)
                    completed_runs.append(current_entry)
                    current_entry = None

        if not completed_runs:
            return False, {}, [
                f"No runs found for cohort '{cohort_id}' in COHORT-DECISIONS.md. "
                "Run the cohort at least once before publishing."
            ]

        successful = [r for r in completed_runs if r["outcome"].lower() == "completed"]
        if not successful:
            return False, {"runs_found": len(completed_runs), "successful": 0}, [
                f"Found {len(completed_runs)} run(s) for '{cohort_id}' but none with outcome 'completed'"
            ]

        most_recent = successful[-1]
        cost_str = most_recent["cost"]
        cost_match = re.search(r"\$?([\d.]+)", cost_str)
        cost_value = float(cost_match.group(1)) if cost_match else None

        details = {
            "date": most_recent["date"],
            "outcome": most_recent["outcome"],
            "cost": cost_str,
            "cost_usd": cost_value,
            "total_runs": len(completed_runs),
            "successful_runs": len(successful),
        }
        return True, details, []

    # ------------------------------------------------------------------
    # Report rendering
    # ------------------------------------------------------------------

    def _render_report(self, r: ValidationResult) -> str:
        schema_icon = "✅" if r.schema_valid else "❌"
        refs_icon = "✅" if r.references_valid else "❌"
        graph_icon = "✅" if r.graph_valid else "❌"
        run_icon = "✅" if r.test_run_verified else "❌"

        lines = [
            "---",
            f"kind: validation-report",
            f"cohort_id: {r.cohort_id}",
            f"cohort_version: {r.cohort_version}",
            f"validated_at: {r.validated_at}",
            f"validator_version: 1.0.0",
            f"status: {r.status}",
            f"schema_valid: {str(r.schema_valid).lower()}",
            f"references_valid: {str(r.references_valid).lower()}",
            f"graph_valid: {str(r.graph_valid).lower()}",
            f"test_run_verified: {str(r.test_run_verified).lower()}",
            "---",
            "",
            f"# Validation Report — {r.cohort_id} v{r.cohort_version}",
            "",
            f"## Schema Validation {schema_icon}",
        ]

        if r.schema_valid:
            lines.append("All required fields present. Types valid.")
        else:
            schema_issues = [f for f in r.findings
                             if any(kw in f for kw in ["Missing required", "kind must", "coordination.", "sla."])]
            for issue in schema_issues:
                lines.append(f"- {issue}")

        lines += [
            "",
            f"## Reference Validation {refs_icon}",
            "| Reference | Kind | Status |",
            "|---|---|---|",
        ]
        for ref in r.reference_details:
            status_icon = "✅ found" if ref["status"] == "found" else "❌ missing"
            lines.append(f"| {ref['id']} | {ref['kind']} | {status_icon} |")

        lines += [
            "",
            f"## Graph Validation {graph_icon}",
        ]
        if r.graph_valid:
            lines.append("Graph structure valid — all edges reference declared nodes.")
        else:
            graph_issues = [f for f in r.findings
                            if any(kw in f for kw in ["Graph node", "Graph has", "runtime_routing"])]
            for issue in graph_issues:
                lines.append(f"- {issue}")

        lines += [
            "",
            f"## Test Run Verification {run_icon}",
            "| Field | Value |",
            "|---|---|",
        ]
        if r.test_run_details:
            td = r.test_run_details
            lines.append(f"| Most recent run | {td.get('date', 'N/A')} |")
            lines.append(f"| Outcome | {td.get('outcome', 'N/A')} |")
            lines.append(f"| Cost | {td.get('cost', 'N/A')} |")
            lines.append(f"| Total runs | {td.get('total_runs', 0)} |")
            lines.append(f"| Successful runs | {td.get('successful_runs', 0)} |")
        else:
            lines.append("| Status | No runs found |")

        lines += [
            "",
            "## Findings",
        ]
        if r.findings:
            for i, finding in enumerate(r.findings, 1):
                lines.append(f"{i}. {finding}")
        else:
            lines.append("None.")

        lines += [
            "",
            "## Recommendation",
        ]
        if r.status == "passed":
            lines.append("✅ Ready for shared marketplace publishing.")
        elif r.status == "warning":
            lines.append(
                "⚠️ Schema, references, and graph are valid but no successful test run recorded. "
                "Run the cohort at least once before publishing."
            )
        else:
            lines.append("❌ Fix findings before publishing.")

        lines += [
            "",
            "Set `provenance.marketplace_listed: true` in the manifest to publish.",
            "",
            "---",
            "*Generated by arcium.marketplace.validator v1.0.0*",
            "*Future: quality-gate-cohort will supersede this report with deeper evaluation.*",
        ]

        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_raw_frontmatter(self, cohort_id: str) -> dict:
        """Load raw frontmatter dict from cohort manifest without CohortManifest parsing."""
        from ..workflow.skill_injector import _parse_frontmatter
        path = self._resolver._cohort_index[cohort_id]
        fm, _ = _parse_frontmatter(path.read_text())
        return fm


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Validate an Arcium cohort for marketplace publishing"
    )
    parser.add_argument("cohort_id", help="Cohort ID to validate")
    parser.add_argument(
        "--vault-path",
        default=str(Path.home() / "Documents" / "arcium-vault"),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write validation report to cohort directory",
    )
    args = parser.parse_args()

    validator = MarketplaceValidator(args.vault_path)
    result = validator.validate(args.cohort_id)

    print(f"\nValidation: {args.cohort_id} v{result.cohort_version}")
    print(f"Status:     {result.status.upper()}")
    print(f"Schema:     {'✅' if result.schema_valid else '❌'}")
    print(f"References: {'✅' if result.references_valid else '❌'}")
    print(f"Graph:      {'✅' if result.graph_valid else '❌'}")
    print(f"Test run:   {'✅' if result.test_run_verified else '❌'}")

    if result.findings:
        print("\nFindings:")
        for f in result.findings:
            print(f"  • {f}")

    if args.write_report:
        resolver = CohortManifestResolver(args.vault_path)
        cohort_path = resolver._cohort_index.get(args.cohort_id)
        if cohort_path:
            report_path = validator.write_report(result, cohort_path.parent)
            print(f"\nReport written: {report_path}")
        else:
            print(f"\nCould not find cohort directory for '{args.cohort_id}'")
