"""Vault file operation tools."""

import re
from pathlib import Path
from typing import List, Dict, Optional, Any


class VaultTools:
    """Tools for interacting with the Obsidian vault."""

    def __init__(self, vault_path: Path):
        """Initialize vault tools.

        Args:
            vault_path: Path to the vault root directory.
        """
        self.vault_path = vault_path

    def _resolve_path(self, relative_path: str) -> Path:
        """Resolve and validate a path within the vault.

        Args:
            relative_path: Relative path from vault root.

        Returns:
            Absolute resolved path.

        Raises:
            ValueError: If path escapes vault directory.
        """
        full_path = (self.vault_path / relative_path).resolve()

        # Ensure path is within vault
        try:
            full_path.relative_to(self.vault_path)
        except ValueError:
            raise ValueError(f"Path escapes vault directory: {relative_path}")

        return full_path

    def read_file(self, path: str) -> str:
        """Read a file from the vault.

        Args:
            path: Relative path from vault root.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If path is invalid.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        return file_path.read_text(encoding='utf-8')

    def write_file(self, path: str, content: str) -> str:
        """Write or overwrite a file in the vault.

        Args:
            path: Relative path from vault root.
            content: Content to write.

        Returns:
            Success message.

        Raises:
            ValueError: If path is invalid.
        """
        file_path = self._resolve_path(path)

        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding='utf-8')

        return f"Successfully wrote to {path}"

    def append_file(self, path: str, content: str) -> str:
        """Append content to an existing file.

        Args:
            path: Relative path from vault root.
            content: Content to append.

        Returns:
            Success message.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If path is invalid.
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully appended to {path}"

    def list_files(self, pattern: Optional[str] = None) -> List[str]:
        """List files in the vault.

        Args:
            pattern: Optional glob pattern (e.g., "*.md", "**/*.md").
                    If None, lists all files recursively.

        Returns:
            List of relative file paths.
        """
        if pattern is None:
            pattern = "**/*"

        # Get all matching paths
        paths = self.vault_path.glob(pattern)

        # Filter to files only and make relative to vault root
        files = [
            str(p.relative_to(self.vault_path))
            for p in paths
            if p.is_file()
        ]

        return sorted(files)

    def search_content(
        self,
        query: str,
        file_pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search file contents using regex.

        Args:
            query: Search pattern (regex supported).
            file_pattern: Optional glob pattern to limit search scope.

        Returns:
            List of matches with structure:
            {
                "file": relative file path,
                "line_number": line number (1-indexed),
                "line": matching line content,
                "match": the matched text
            }
        """
        # Get files to search
        files = self.list_files(file_pattern)

        # Compile regex pattern
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {e}")

        matches = []

        for file_path in files:
            try:
                content = self.read_file(file_path)
                lines = content.splitlines()

                for line_num, line in enumerate(lines, start=1):
                    match = pattern.search(line)
                    if match:
                        matches.append({
                            "file": file_path,
                            "line_number": line_num,
                            "line": line.strip(),
                            "match": match.group(0)
                        })
            except Exception:
                # Skip files that can't be read
                continue

        return matches
