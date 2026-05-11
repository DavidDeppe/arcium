"""Configuration management for the Arcium MCP server."""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Manages server configuration.

    Resolution order for vault_path:
      1. Explicit config_path argument pointing to a config.json
      2. config.json in project root (if present)
      3. ARCIUM_VAULT_PATH environment variable
      4. ~/Documents/arcium-vault (default)

    config.json is optional — a missing file is not an error.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to config.json file. Defaults to project root.
                         If absent, falls back to env var then default path.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config.json"

        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from config.json if present, otherwise return empty dict."""
        if not self.config_path.exists():
            return {}

        import json
        with open(self.config_path, 'r') as f:
            return json.load(f)

    @property
    def vault_path(self) -> Path:
        """Get the configured vault path.

        Resolution order:
          1. vault_path key in config.json
          2. ARCIUM_VAULT_PATH environment variable
          3. ~/Documents/arcium-vault
        """
        raw = (
            self._config.get('vault_path')
            or os.getenv('ARCIUM_VAULT_PATH')
            or str(Path.home() / 'Documents' / 'arcium-vault')
        )
        path = Path(raw).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Vault path does not exist: {path}\n"
                "Set vault_path in config.json or ARCIUM_VAULT_PATH environment variable."
            )

        if not path.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {path}")

        return path
