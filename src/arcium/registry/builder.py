"""
Registry Builder — scans the vault marketplace and builds _registry/index.json.

Rebuilds the flat lookup table:
  artifact_id@version → {path, kind, hash, tier, description}

Run manually or via Git hook on vault push.
Usage: python -m arcium.registry.builder [--vault-path PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown. Returns (frontmatter_dict, body)."""
    if not content.startswith("---"):
        return {}, content

    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    yaml_block = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")

    try:
        parsed = yaml.safe_load(yaml_block) or {}
    except yaml.YAMLError:
        return {}, content

    return parsed if isinstance(parsed, dict) else {}, body


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_registry(vault_path: Path) -> dict:
    """
    Scan marketplace directories and build artifact index.

    Returns the complete index dict (not yet written to disk).
    """
    marketplace = vault_path / "02-marketplace"

    scan_dirs = [
        marketplace / "agents",
        marketplace / "skills",
        marketplace / "tools",
        marketplace / "cohorts",
    ]

    artifacts: dict = {}
    counts: dict[str, int] = {}

    for scan_dir in scan_dirs:
        if not scan_dir.exists():
            continue

        for md_file in sorted(scan_dir.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            frontmatter, _ = _parse_frontmatter(content)

            artifact_id = frontmatter.get("id")
            version = frontmatter.get("version")
            kind = frontmatter.get("kind")

            if not artifact_id or not version or not kind:
                continue

            key = f"{artifact_id}@{version}"
            # vault-relative path (forward slashes, no leading slash)
            rel_path = md_file.relative_to(vault_path).as_posix()

            entry = {
                "id": artifact_id,
                "version": str(version),
                "kind": kind,
                "tier": frontmatter.get("tier", "unknown"),
                "description": frontmatter.get("description", ""),
                "path": rel_path,
                "sha256": _sha256(content),
            }

            artifacts[key] = entry
            counts[kind] = counts.get(kind, 0) + 1

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "artifacts": artifacts,
    }, counts


def write_registry(vault_path: Path, index: dict) -> Path:
    """Write index.json to 02-marketplace/_registry/ and return the path."""
    registry_dir = vault_path / "02-marketplace" / "_registry"
    registry_dir.mkdir(parents=True, exist_ok=True)

    out_path = registry_dir / "index.json"
    out_path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return out_path


def main(vault_path: Path) -> None:
    index, counts = build_registry(vault_path)
    out_path = write_registry(vault_path, index)

    total = sum(counts.values())
    print(f"Registry built: {total} artifacts")
    for kind in sorted(counts):
        print(f"  {kind}: {counts[kind]}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Arcium marketplace registry builder")
    parser.add_argument(
        "--vault-path",
        default=str(Path.home() / "Documents" / "arcium-vault"),
        help="Path to the Arcium vault root",
    )
    args = parser.parse_args()

    vault = Path(args.vault_path).expanduser().resolve()
    if not vault.exists():
        print(f"ERROR: vault path does not exist: {vault}", file=sys.stderr)
        sys.exit(1)

    main(vault)
