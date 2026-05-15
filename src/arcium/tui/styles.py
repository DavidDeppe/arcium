"""
Shared Rich theme and styling for the Arcium TUI.
Matches Arcium's dark color palette.
"""
from rich.theme import Theme
from rich.console import Console

ARCIUM_THEME = Theme({
    "arcium.title":    "bold rgb(206,203,246)",   # purple-ish white
    "arcium.subtitle": "rgb(175,169,236)",          # purple
    "arcium.teal":     "rgb(93,202,165)",            # teal — agents
    "arcium.amber":    "rgb(210,145,40)",            # amber — critic/cohort
    "arcium.coral":    "rgb(240,153,123)",           # coral — engineer
    "arcium.blue":     "rgb(70,130,200)",            # blue — vault
    "arcium.muted":    "rgb(156,154,146)",           # muted gray
    "arcium.success":  "bold rgb(93,202,165)",       # success green
    "arcium.warning":  "bold rgb(210,145,40)",       # warning amber
    "arcium.error":    "bold rgb(240,80,80)",        # error red
    "arcium.prompt":   "rgb(206,203,246)",           # prompt purple
})

console = Console(theme=ARCIUM_THEME)


def print_header() -> None:
    """Print the Arcium TUI header banner."""
    console.print()
    console.print(
        "  [arcium.title]Arcium[/] [arcium.muted]—[/] "
        "[arcium.subtitle]enterprise agentic coordination platform[/]"
    )
    console.print(
        "  [arcium.muted]CAST framework: "
        "[arcium.subtitle]Cohort[/] · "
        "[arcium.teal]Agent[/] · "
        "[arcium.blue]Skill[/] · "
        "[arcium.amber]Tool[/][/]"
    )
    console.print()


def print_section(title: str, color: str = "arcium.title") -> None:
    console.print(f"  [{color}]── {title}[/]")
    console.print()


def success(msg: str) -> None:
    console.print(f"  [arcium.success]✓[/] {msg}")


def warning(msg: str) -> None:
    console.print(f"  [arcium.warning]⚠[/] {msg}")


def error(msg: str) -> None:
    console.print(f"  [arcium.error]✗[/] {msg}")


def info(msg: str) -> None:
    console.print(f"  [arcium.muted]{msg}[/]")
