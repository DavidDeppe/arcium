"""
GraphExecutor — manifest-driven routing engine for Arcium cohort coordination.

Reads routing decisions from agent verdict file YAML frontmatter.
Validates routing decisions against the cohort manifest's declared graph edges.
Falls back to default_next if no route_to is declared or if routing is invalid.

Routing contract:
  Agents express routing intent via YAML frontmatter in their verdict files:
    route_to: <node-id>
    route_reason: <one sentence>

  The executor:
    1. Reads the verdict file frontmatter after agent completion
    2. Extracts route_to (optional field)
    3. Validates against valid_routes for current node
    4. If valid: honors the routing decision
    5. If invalid or absent: uses default_next
    6. Enforces max_iterations — escalates to human if exceeded

Phase 3b scope: routing decisions only.
Graph execution sequencing (replacing CohortCoordinator phase methods) is Phase 4+.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Union

import yaml

from .cohort_resolver import CohortManifest, GraphNode, RoleNotFoundError

logger = logging.getLogger(__name__)

_ESCALATE = "__escalate__"


class GraphExecutorError(Exception):
    """Raised for manifest graph configuration errors (not routing fallbacks)."""
    pass


class GraphExecutor:
    """
    Manifest-driven routing engine for cohort coordination.

    Resolves the next node to execute given the current node and an optional
    verdict file. Validates agent routing directives against the manifest graph.
    """

    def __init__(self, manifest: CohortManifest, vault_path: Union[str, Path]):
        self.manifest = manifest
        self.vault_path = Path(vault_path)
        self._iteration_counts: dict[str, int] = {}
        self._routing_log: list[dict] = []

    def resolve_next_node(
        self,
        current_node_id: str,
        verdict_file_path: str | None = None,
    ) -> str | None:
        """
        Resolve the next node after current_node_id completes.

        Returns:
            str: next node id to execute
            None: current node is terminal, coordination complete
            '__escalate__': max_iterations exceeded, human escalation required
        """
        node = self.manifest.graph_nodes.get(current_node_id)
        if node is None:
            raise GraphExecutorError(
                f"Node '{current_node_id}' not found in manifest graph for '{self.manifest.id}'. "
                f"Available nodes: {list(self.manifest.graph_nodes.keys())}"
            )

        if node.terminal:
            self._routing_log.append({
                "from": current_node_id,
                "to": None,
                "reason": "terminal node",
                "source": "default",
                "iteration": self._iteration_counts.get(current_node_id, 0) + 1,
            })
            return None

        # Increment visit count
        self._iteration_counts[current_node_id] = self._iteration_counts.get(current_node_id, 0) + 1
        current_iteration = self._iteration_counts[current_node_id]

        # Check max_iterations
        max_iter = self.manifest.coordination.get("max_iterations", 5)
        if current_iteration > max_iter:
            self._routing_log.append({
                "from": current_node_id,
                "to": _ESCALATE,
                "reason": f"max_iterations ({max_iter}) exceeded",
                "source": "escalate",
                "iteration": current_iteration,
            })
            return _ESCALATE

        # Attempt to read agent routing directive from verdict file
        agent_route = None
        agent_reason = ""
        if verdict_file_path:
            try:
                frontmatter = self._read_frontmatter(verdict_file_path)
                agent_route = frontmatter.get("route_to")
                agent_reason = frontmatter.get("route_reason", "")
            except Exception as e:
                logger.warning("Could not read verdict file '%s': %s", verdict_file_path, e)

        # Validate agent routing directive
        if agent_route is not None:
            if agent_route in node.valid_routes:
                self._routing_log.append({
                    "from": current_node_id,
                    "to": agent_route,
                    "reason": agent_reason or "agent directive",
                    "source": "agent",
                    "iteration": current_iteration,
                })
                return agent_route
            else:
                logger.warning(
                    "Node '%s' requested route_to '%s' which is not in valid_routes %s — "
                    "falling back to default_next '%s'",
                    current_node_id, agent_route, node.valid_routes, node.default_next,
                )

        # Fall back to default_next
        self._routing_log.append({
            "from": current_node_id,
            "to": node.default_next,
            "reason": "default routing" if agent_route is None else f"invalid route '{agent_route}' — using default",
            "source": "default",
            "iteration": current_iteration,
        })
        return node.default_next

    def get_routing_log(self) -> list[dict]:
        """Return the accumulated routing log for this executor instance."""
        return list(self._routing_log)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_frontmatter(self, file_path: str) -> dict:
        """
        Read YAML frontmatter from a markdown file.
        Handles both vault-relative paths and absolute paths.
        """
        path = Path(file_path)
        if not path.is_absolute():
            path = self.vault_path / file_path

        content = path.read_text()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if not match:
            return {}
        return yaml.safe_load(match.group(1)) or {}


# ---------------------------------------------------------------------------
# Inline unit tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys
    import tempfile

    vault = os.path.expanduser("~/Documents/arcium-vault")

    from arcium.workflow.cohort_resolver import CohortManifestResolver
    resolver = CohortManifestResolver(vault)
    manifest = resolver.load_manifest("poc-generator")

    passed = 0
    failed = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        global passed, failed
        status = "PASS" if condition else "FAIL"
        suffix = f": {detail}" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        if condition:
            passed += 1
        else:
            failed += 1

    print("GraphExecutor — unit tests")
    print("=" * 60)

    # Test 1: terminal node returns None
    executor = GraphExecutor(manifest, vault)
    result = executor.resolve_next_node("communications-specialist")
    check("T1: terminal node returns None", result is None, f"got {result!r}")

    # Test 2: default routing when no verdict file
    executor2 = GraphExecutor(manifest, vault)
    result2 = executor2.resolve_next_node("team-lead")
    check("T2: default routing works", result2 == "senior-architect", f"got {result2!r}")

    # Test 3: valid agent routing honored
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            "---\nverdict: PASS_WITH_CONDITIONS\n"
            "route_to: senior-architect\nroute_reason: design gap\n---\n\nFindings here."
        )
        tmp_path = f.name
    executor3 = GraphExecutor(manifest, vault)
    result3 = executor3.resolve_next_node("solutions-critic", tmp_path)
    check("T3: valid agent routing honored", result3 == "senior-architect", f"got {result3!r}")

    # Test 4: invalid route falls back to default
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("---\nverdict: FAIL\nroute_to: nonexistent-agent\n---\n\nFindings.")
        tmp_path4 = f.name
    executor4 = GraphExecutor(manifest, vault)
    result4 = executor4.resolve_next_node("solutions-critic", tmp_path4)
    check(
        "T4: invalid route falls back to default",
        result4 == "communications-specialist",
        f"got {result4!r}",
    )

    # Test 5: max_iterations triggers escalation
    executor5 = GraphExecutor(manifest, vault)
    max_iter = manifest.coordination["max_iterations"]
    executor5._iteration_counts["solutions-critic"] = max_iter
    result5 = executor5.resolve_next_node("solutions-critic")
    check("T5: max_iterations triggers escalation", result5 == _ESCALATE, f"got {result5!r}")

    # Test 6: routing log populated correctly
    log = executor3.get_routing_log()
    check(
        "T6: routing log correct",
        len(log) == 1 and log[0]["source"] == "agent" and log[0]["to"] == "senior-architect",
        f"log={log}",
    )

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
