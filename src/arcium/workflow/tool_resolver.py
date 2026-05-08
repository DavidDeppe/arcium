"""
Tool manifest resolver for the WAT pipeline.

Reads TOOL.md manifests and _bundles.yaml from the vault and resolves
bundle names to --allowedTools CLI arguments for ClaudeCodeAgent.
"""

import logging
from pathlib import Path
from typing import List

import yaml

logger = logging.getLogger(__name__)

_TOOLS_DIR = "00-firm/tools"
_BUNDLES_FILE = "00-firm/tools/_bundles.yaml"


class ToolResolverError(Exception):
    """Raised when bundle or tool resolution fails."""
    pass


class ToolManifestResolver:
    """
    Resolves tool bundle names to --allowedTools CLI argument lists.

    Reads tool manifests from <vault_path>/00-firm/tools/ and the bundle
    index from <vault_path>/00-firm/tools/_bundles.yaml.

    Each TOOL.md manifest's frontmatter `mcp.endpoints_allowed` field lists
    the MCP function names exposed by that tool. resolve() combines these
    across all tools in a bundle and returns fully-qualified MCP endpoint
    strings in the format expected by the claude --allowedTools flag:

        mcp__<server>__<function_name>

    where <server> comes from each manifest's `mcp.server` frontmatter field.
    """

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self._bundle_cache: dict = {}
        self._manifest_cache: dict = {}

    def _load_bundles(self) -> dict:
        """Load and cache _bundles.yaml."""
        if self._bundle_cache:
            return self._bundle_cache

        bundles_path = self.vault_path / _BUNDLES_FILE
        if not bundles_path.exists():
            raise ToolResolverError(
                f"Bundle index not found: {bundles_path}. "
                "Expected file: 00-firm/tools/_bundles.yaml"
            )

        with open(bundles_path) as f:
            raw = yaml.safe_load(f) or {}

        bundles = raw.get("bundles", {})
        if not bundles:
            raise ToolResolverError(
                f"_bundles.yaml loaded but contains no 'bundles' key: {bundles_path}"
            )

        self._bundle_cache = bundles
        return bundles

    def _load_manifest(self, tool_id: str) -> dict:
        """Load and cache a single TOOL.md manifest's frontmatter."""
        if tool_id in self._manifest_cache:
            return self._manifest_cache[tool_id]

        manifest_path = self.vault_path / _TOOLS_DIR / f"{tool_id}.md"
        if not manifest_path.exists():
            raise ToolResolverError(
                f"Tool manifest not found: {manifest_path} (tool id: '{tool_id}')"
            )

        content = manifest_path.read_text()

        if not content.startswith("---"):
            raise ToolResolverError(
                f"Tool manifest has no frontmatter: {manifest_path}"
            )

        end = content.find("\n---", 3)
        if end == -1:
            raise ToolResolverError(
                f"Tool manifest has unclosed frontmatter delimiter: {manifest_path}"
            )

        yaml_block = content[3:end].strip()
        try:
            frontmatter = yaml.safe_load(yaml_block) or {}
        except yaml.YAMLError as e:
            raise ToolResolverError(
                f"Malformed YAML frontmatter in {manifest_path}: {e}"
            ) from e

        if not isinstance(frontmatter, dict):
            raise ToolResolverError(
                f"Frontmatter in {manifest_path} is not a dict"
            )

        self._manifest_cache[tool_id] = frontmatter
        return frontmatter

    def resolve(self, bundle_name: str) -> List[str]:
        """
        Resolve a bundle name to a list of fully-qualified MCP endpoint strings.

        Args:
            bundle_name: Bundle key from _bundles.yaml (e.g. 'vault_only', 'all')

        Returns:
            List of strings in the format 'mcp__<server>__<function>'
            e.g. ['mcp__arcium__vault__read_file', 'mcp__arcium__vault__write_file', ...]

        Raises:
            ToolResolverError: If the bundle or any tool manifest cannot be resolved
        """
        bundles = self._load_bundles()

        if bundle_name not in bundles:
            available = list(bundles.keys())
            raise ToolResolverError(
                f"Unknown bundle '{bundle_name}'. Available bundles: {available}"
            )

        bundle = bundles[bundle_name]
        tool_ids = bundle.get("tools", [])

        if not tool_ids:
            raise ToolResolverError(
                f"Bundle '{bundle_name}' has no tools defined"
            )

        endpoints = []
        for tool_id in tool_ids:
            manifest = self._load_manifest(tool_id)

            mcp = manifest.get("mcp")
            if not mcp or not isinstance(mcp, dict):
                raise ToolResolverError(
                    f"Tool manifest '{tool_id}.md' is missing 'mcp' block"
                )

            server = mcp.get("server")
            if not server:
                raise ToolResolverError(
                    f"Tool manifest '{tool_id}.md' is missing 'mcp.server'"
                )

            allowed = mcp.get("endpoints_allowed", [])
            if not allowed:
                raise ToolResolverError(
                    f"Tool manifest '{tool_id}.md' has empty 'mcp.endpoints_allowed'"
                )

            for fn in allowed:
                endpoints.append(f"mcp__{server}__{fn}")

        logger.debug("Resolved bundle '%s' → %d endpoints", bundle_name, len(endpoints))
        return endpoints

    def resolve_to_cli_args(self, bundle_name: str) -> List[str]:
        """
        Resolve a bundle to --allowedTools CLI argument fragments.

        Returns a two-element list ready to extend a subprocess command:
            ['--allowedTools', 'mcp__arcium__vault__read_file,...']

        Args:
            bundle_name: Bundle key from _bundles.yaml

        Returns:
            ['--allowedTools', '<comma-joined endpoints>']
        """
        endpoints = self.resolve(bundle_name)
        return ["--allowedTools", ",".join(endpoints)]


if __name__ == "__main__":
    import os
    import sys

    vault_path = os.getenv(
        "ARCIUM_VAULT_PATH",
        str(Path.home() / "Documents" / "arcium-vault")
    )

    resolver = ToolManifestResolver(vault_path=vault_path)
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

    print("ToolManifestResolver — unit tests")
    print("=" * 50)

    # Test 1: vault_only resolves to exactly 5 endpoints
    try:
        vault_endpoints = resolver.resolve("vault_only")
        check("vault_only has 5 endpoints", len(vault_endpoints) == 5,
              f"got {len(vault_endpoints)}: {vault_endpoints}")
    except ToolResolverError as e:
        check("vault_only has 5 endpoints", False, str(e))

    # Test 2: all resolves to exactly 12 endpoints
    try:
        all_endpoints = resolver.resolve("all")
        check("all has 12 endpoints", len(all_endpoints) == 12,
              f"got {len(all_endpoints)}: {all_endpoints}")
    except ToolResolverError as e:
        check("all has 12 endpoints", False, str(e))

    # Test 3: vault_only endpoints all start with mcp__arcium__vault__
    try:
        vault_endpoints = resolver.resolve("vault_only")
        all_vault = all(ep.startswith("mcp__arcium__vault__") for ep in vault_endpoints)
        check("vault_only endpoints all start with mcp__arcium__vault__", all_vault,
              str(vault_endpoints))
    except ToolResolverError as e:
        check("vault_only endpoints all start with mcp__arcium__vault__", False, str(e))

    # Test 4: resolve_to_cli_args returns ['--allowedTools', '<csv>'] with 5 entries
    try:
        cli_args = resolver.resolve_to_cli_args("vault_only")
        check(
            "resolve_to_cli_args is ['--allowedTools', '<csv>']",
            len(cli_args) == 2 and cli_args[0] == "--allowedTools",
            str(cli_args)
        )
        csv_count = len(cli_args[1].split(","))
        check("resolve_to_cli_args CSV has 5 entries", csv_count == 5,
              f"got {csv_count}")
    except ToolResolverError as e:
        check("resolve_to_cli_args is ['--allowedTools', '<csv>']", False, str(e))
        check("resolve_to_cli_args CSV has 5 entries", False, str(e))

    # Test 5: unknown bundle raises ToolResolverError
    try:
        resolver.resolve("nonexistent_bundle")
        check("unknown bundle raises ToolResolverError", False, "no exception raised")
    except ToolResolverError:
        check("unknown bundle raises ToolResolverError", True)
    except Exception as e:
        check("unknown bundle raises ToolResolverError", False,
              f"wrong exception: {type(e).__name__}: {e}")

    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
