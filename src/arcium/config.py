"""
Environment configuration for Arcium.

Centralizes loading of environment variables with sensible defaults.
No hardcoded user-specific paths anywhere.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


@dataclass
class ArciumConfig:
    """
    Centralized configuration for Arcium paths and settings.

    All values loaded from environment variables with sensible defaults.
    """

    # MCP Configuration
    mcp_config_path: str

    # Vault Configuration
    vault_path: str

    # Projects Configuration
    projects_path: str

    # Reasoning Logs
    reasoning_log_dir: str

    # API Keys
    anthropic_api_key: Optional[str]

    # Mode Configuration
    dev_mode: bool

    # Execution mode: "autonomous" (ClaudeCodeAgent) or "api" (ReactAgent via AnthropicBackend)
    execution_mode: str

    @classmethod
    def from_env(cls) -> "ArciumConfig":
        """
        Load configuration from environment variables.

        Environment Variables:
            ARCIUM_MCP_CONFIG: Path to .mcp.json (default: ./.mcp.json)
            ARCIUM_VAULT_PATH: Path to Obsidian vault (default: ~/Documents/arcium-vault)
            ARCIUM_PROJECTS_PATH: Path to projects directory (default: ~/projects)
            ARCIUM_REASONING_LOG_DIR: Path to reasoning logs (default: <vault>/06-findings)
            ANTHROPIC_API_KEY: Anthropic API key (optional)
            DEV_MODE: Use DEV mode (Haiku, lower cost limits) (default: false)
            ARCIUM_EXECUTION_MODE: Agent backend — "autonomous" (ClaudeCodeAgent) or "api" (ReactAgent) (default: autonomous)

        Returns:
            ArciumConfig instance
        """
        # MCP config path
        mcp_config_path = os.getenv(
            'ARCIUM_MCP_CONFIG',
            str(Path.cwd() / '.mcp.json')
        )

        # Vault path
        vault_path = os.getenv(
            'ARCIUM_VAULT_PATH',
            str(Path.home() / 'Documents' / 'arcium-vault')
        )

        # Projects path
        projects_path = os.getenv(
            'ARCIUM_PROJECTS_PATH',
            str(Path.home() / 'projects')
        )

        # Reasoning log directory (defaults to vault/06-findings)
        reasoning_log_dir = os.getenv(
            'ARCIUM_REASONING_LOG_DIR',
            str(Path(vault_path) / '06-findings')
        )

        # API key
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')

        # Dev mode
        dev_mode = os.getenv('DEV_MODE', 'false').lower() == 'true'

        # Execution mode
        execution_mode = os.getenv('ARCIUM_EXECUTION_MODE', 'autonomous').lower()
        if execution_mode not in ('autonomous', 'api'):
            execution_mode = 'autonomous'

        return cls(
            mcp_config_path=mcp_config_path,
            vault_path=vault_path,
            projects_path=projects_path,
            reasoning_log_dir=reasoning_log_dir,
            anthropic_api_key=anthropic_api_key,
            dev_mode=dev_mode,
            execution_mode=execution_mode
        )

    def validate(self) -> None:
        """
        Validate that required paths exist.

        Raises:
            FileNotFoundError: If required paths don't exist
        """
        # MCP config must exist
        if not Path(self.mcp_config_path).exists():
            raise FileNotFoundError(
                f"MCP config not found: {self.mcp_config_path}\n"
                f"Set ARCIUM_MCP_CONFIG or create .mcp.json in current directory"
            )

        # Vault must exist
        if not Path(self.vault_path).exists():
            raise FileNotFoundError(
                f"Vault path not found: {self.vault_path}\n"
                f"Set ARCIUM_VAULT_PATH environment variable"
            )

        # Create projects path if it doesn't exist
        Path(self.projects_path).mkdir(parents=True, exist_ok=True)

        # Create reasoning log dir if it doesn't exist
        Path(self.reasoning_log_dir).mkdir(parents=True, exist_ok=True)


# Global config instance (lazy-loaded)
_config: Optional[ArciumConfig] = None


def get_config() -> ArciumConfig:
    """
    Get the global ArciumConfig instance.

    Loads from environment on first call, returns cached instance on subsequent calls.

    Returns:
        ArciumConfig instance

    Raises:
        FileNotFoundError: If required paths don't exist
    """
    global _config

    if _config is None:
        _config = ArciumConfig.from_env()
        _config.validate()

    return _config


def reset_config() -> None:
    """
    Reset the global config instance.

    Useful for testing or when environment variables change.
    """
    global _config
    _config = None
