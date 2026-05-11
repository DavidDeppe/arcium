"""
VaultSyncAgent — lightweight sync service for federated vault management.

Responsibilities:
  PULL: Sync 01-firm-context/ and 02-marketplace/ from parent vault
  PUSH: Submit 07-sync-outbox/ contents as PR to parent vault

Phase 4 scope: pull sync only (no parent vault configured yet).
Push sync (outbox → PR) is stubbed for Phase 5.

Not a cohort — this is a background service with no LLM calls.
Run manually or on schedule via cron/launchd.

Usage: python -m arcium.sync.agent [--vault-path PATH] [--dry-run]
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_SYNC_DIRS = ["01-firm-context", "02-marketplace"]


@dataclass
class SyncReport:
    pulled: int = 0
    pushed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        mode = "[DRY RUN] " if self.dry_run else ""
        return (
            f"{mode}Sync complete: "
            f"{self.pulled} pulled, {self.pushed} pushed, "
            f"{self.skipped} skipped, {len(self.errors)} errors"
        )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class VaultSyncAgent:
    """
    Lightweight sync agent for federated vault management.

    Reads .vault-config.yaml to determine sync configuration.
    Phase 4: pull sync only. Push sync stubbed for Phase 5.
    """

    def __init__(self, vault_path: str | Path):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.config = self._load_config()

    def _load_config(self) -> dict:
        config_path = self.vault_path / ".vault-config.yaml"
        if not config_path.exists():
            raise FileNotFoundError(
                f".vault-config.yaml not found at {config_path}. "
                "Run 'arcium vault init' or create the file manually."
            )
        with open(config_path) as f:
            return yaml.safe_load(f) or {}

    def pull(self, dry_run: bool = False) -> SyncReport:
        """
        Pull updates from parent vault into local vault.

        Compares SHA256 hashes of files in sync.pull_from source dirs against
        local copies. Copies files that are missing or changed.

        Returns SyncReport with counts.
        """
        report = SyncReport(dry_run=dry_run)

        sync_cfg = self.config.get("sync", {})
        pull_from: list = sync_cfg.get("pull_from", [])
        parent: str | None = self.config.get("parent")

        if not parent and not pull_from:
            logger.info("No parent vault configured — pull sync skipped")
            print("No parent vault configured — pull sync skipped")
            return report

        for source_spec in pull_from:
            source_vault = Path(source_spec.get("vault", "")).expanduser()
            dirs = source_spec.get("dirs", _SYNC_DIRS)

            if not source_vault.exists():
                msg = f"Source vault not found: {source_vault}"
                logger.warning(msg)
                report.errors.append(msg)
                continue

            for sync_dir in dirs:
                source_dir = source_vault / sync_dir
                dest_dir = self.vault_path / sync_dir

                if not source_dir.exists():
                    logger.debug("Source dir does not exist, skipping: %s", source_dir)
                    continue

                for src_file in sorted(source_dir.rglob("*.md")):
                    rel = src_file.relative_to(source_vault)
                    dest_file = self.vault_path / rel

                    if dest_file.exists() and _sha256_file(src_file) == _sha256_file(dest_file):
                        report.skipped += 1
                        continue

                    if dry_run:
                        action = "NEW" if not dest_file.exists() else "UPDATE"
                        print(f"  [DRY RUN] {action}: {rel}")
                        report.pulled += 1
                    else:
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_file, dest_file)
                        logger.info("Pulled: %s", rel)
                        report.pulled += 1

        return report

    def push(self, dry_run: bool = False) -> SyncReport:
        """
        Push outbox contents to parent vault as a PR.

        Phase 5 stub — not yet implemented.
        Stage findings in 07-sync-outbox/ manually for now.
        """
        report = SyncReport(dry_run=dry_run)
        logger.info("Push sync not yet implemented — stage findings in 07-sync-outbox/ manually")
        print("Push sync not yet implemented — stage findings in 07-sync-outbox/ manually")
        return report


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Arcium Vault Sync Agent")
    parser.add_argument(
        "--vault-path",
        default=str(Path.home() / "Documents" / "arcium-vault"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pull", action="store_true", default=True)
    args = parser.parse_args()

    agent = VaultSyncAgent(args.vault_path)
    if args.pull:
        report = agent.pull(dry_run=args.dry_run)
        print(report.summary())
