"""arcium run — non-interactive cohort runner for scripting."""

import sys
import argparse


def run_cohort_cli(args: list[str]) -> None:
    parser = argparse.ArgumentParser(
        prog="arcium run",
        description="Run an Arcium cohort",
    )
    parser.add_argument("--idea", required=True, help="One-sentence idea or task")
    parser.add_argument("--slug", required=True, help="Project slug (kebab-case)")
    parser.add_argument(
        "--cohort",
        default="poc-generator",
        help="Cohort ID to run (default: poc-generator)",
    )
    parsed = parser.parse_args(args)

    from arcium.workflow.cohort_coordinator import CohortCoordinator

    coordinator = CohortCoordinator(cohort_id=parsed.cohort)
    coordinator.run(poc_idea=parsed.idea, poc_slug=parsed.slug)
