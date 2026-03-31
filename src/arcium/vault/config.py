"""Configuration management for the Arcium MCP server."""

import json
from pathlib import Path
from typing import Optional


class Config:
    """Manages server configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to config.json file. Defaults to project root.
        """
        if config_path is None:
            # Default to config.json in project root
            # Go up from src/arcium/vault/config.py to project root
            config_path = Path(__file__).parent.parent.parent.parent / "config.json"

        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                "Please create config.json with vault_path setting."
            )

        with open(self.config_path, 'r') as f:
            config = json.load(f)

        if 'vault_path' not in config:
            raise ValueError("config.json must contain 'vault_path' field")

        return config

    @property
    def vault_path(self) -> Path:
        """Get the configured vault path."""
        path = Path(self._config['vault_path']).expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(f"Vault path does not exist: {path}")

        if not path.is_dir():
            raise NotADirectoryError(f"Vault path is not a directory: {path}")

        return path
