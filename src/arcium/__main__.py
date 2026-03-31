"""Entry point for running Arcium modules.

For backward compatibility, running 'python -m arcium' runs the vault server.
"""

from .vault.server import main

if __name__ == "__main__":
    main()
