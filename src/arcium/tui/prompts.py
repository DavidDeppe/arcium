"""
Reusable questionary prompt helpers for the Arcium TUI.
All prompts use consistent styling and validation.
"""
import re
import questionary
from questionary import Style

ARCIUM_STYLE = Style([
    ("qmark",       "fg:#cecebd bold"),
    ("question",    "fg:#cccbf6 bold"),
    ("answer",      "fg:#5dcaa5 bold"),
    ("pointer",     "fg:#5dcaa5 bold"),
    ("highlighted", "fg:#5dcaa5 bold"),
    ("selected",    "fg:#5dcaa5"),
    ("separator",   "fg:#9c9c8e"),
    ("instruction", "fg:#9c9c8e"),
    ("text",        "fg:#faf9f5"),
    ("disabled",    "fg:#9c9c8e italic"),
])


def ask(message: str, default: str = "") -> str:
    return questionary.text(message, default=default, style=ARCIUM_STYLE).ask()


def ask_required(message: str) -> str | None:
    """Ask for a required field — re-prompts if empty. Returns None if user cancels."""
    while True:
        val = questionary.text(message, style=ARCIUM_STYLE).ask()
        if val is None:
            return None
        if val.strip():
            return val.strip()
        print("  This field is required.")


def ask_kebab(message: str, default: str = "") -> str | None:
    """Ask for a kebab-case id — validates and normalizes. Returns None if user cancels."""
    while True:
        val = questionary.text(message, default=default, style=ARCIUM_STYLE).ask()
        if val is None:
            return None
        if not val.strip():
            continue
        normalized = val.strip().lower().replace(" ", "-")
        normalized = re.sub(r"[^a-z0-9-]", "", normalized)
        if normalized != val.strip():
            print(f"  Normalized to: {normalized}")
        if normalized:
            return normalized


def ask_select(message: str, choices: list) -> str | None:
    return questionary.select(message, choices=choices, style=ARCIUM_STYLE).ask()


def ask_checkbox(message: str, choices: list) -> list | None:
    return questionary.checkbox(message, choices=choices, style=ARCIUM_STYLE).ask()


def ask_confirm(message: str, default: bool = True) -> bool:
    result = questionary.confirm(message, default=default, style=ARCIUM_STYLE).ask()
    return result if result is not None else False


def ask_multiline(message: str) -> str:
    """
    Ask for multi-line text input.
    User types content; enters blank line to finish.
    """
    from arcium.tui.styles import info
    info(f"{message}")
    info("(Enter a blank line when done)")
    lines = []
    while True:
        try:
            line = input("  > ")
        except (EOFError, KeyboardInterrupt):
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)
