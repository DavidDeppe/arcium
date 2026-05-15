"""
Arcium TUI — interactive graph editor.

Presents a matrix showing permitted routing edges between cohort agents.
Sequential chain is the default (safe). Users can add back-routes.

Matrix format:
  Rows = FROM agent
  Cols = TO agent
  ✓ = permitted route
  - = not permitted (or terminal)
"""
import questionary
from rich.table import Table


def build_graph_interactive(role_names: list[str]) -> list[dict]:
    """
    Interactive graph editor for cohort coordination.

    Returns list of GraphNode dicts matching poc-generator.md format.
    """
    from arcium.tui.styles import console, info
    from arcium.tui.prompts import ask_select, ask_confirm, ARCIUM_STYLE

    info("Define which agents can route to which other agents.")
    info("")
    info("Start with a routing preset:")

    preset = ask_select("", choices=[
        questionary.Choice(
            "Sequential chain  (safe default — each agent routes to the next)",
            value="sequential",
        ),
        questionary.Choice(
            "Custom matrix     (define all edges manually)",
            value="custom",
        ),
    ])

    if preset is None:
        preset = "sequential"

    if preset == "sequential":
        edges = _build_sequential_edges(role_names)
    else:
        edges = _build_custom_edges(role_names)

    console.print()
    _print_matrix(role_names, edges)
    console.print()

    while True:
        action = ask_select("Graph looks good?", choices=[
            questionary.Choice("✓  Accept this graph", value="accept"),
            questionary.Choice("+  Add a route",       value="add"),
            questionary.Choice("-  Remove a route",    value="remove"),
        ])

        if action == "accept" or action is None:
            break

        elif action == "add":
            from_role = ask_select("From:", role_names)
            if not from_role:
                continue
            to_choices = [r for r in role_names if r != from_role]
            to_role = ask_select("To:", to_choices)
            if to_role and to_role not in edges.get(from_role, []):
                edges.setdefault(from_role, []).append(to_role)
                from arcium.tui.styles import success
                success(f"Added: {from_role} → {to_role}")

        elif action == "remove":
            existing = [
                f"{f} → {t}"
                for f, tos in edges.items()
                for t in tos
            ]
            if not existing:
                info("No routes to remove.")
            else:
                choice = ask_select("Remove which route?", existing)
                if choice:
                    f, t = choice.split(" → ")
                    if t in edges.get(f, []):
                        edges[f].remove(t)
                        info(f"Removed: {f} → {t}")

        console.print()
        _print_matrix(role_names, edges)
        console.print()

    return _edges_to_graph_nodes(role_names, edges)


def _build_sequential_edges(roles: list[str]) -> dict[str, list[str]]:
    """Sequential chain: each role routes only to the next."""
    edges: dict[str, list[str]] = {}
    for i, role in enumerate(roles[:-1]):
        edges[role] = [roles[i + 1]]
    return edges


def _build_custom_edges(roles: list[str]) -> dict[str, list[str]]:
    """Custom: ask user to check/uncheck each possible edge."""
    from arcium.tui.prompts import ask_checkbox
    from arcium.tui.styles import info

    edges: dict[str, list[str]] = {}
    info("For each agent, select which agents it can route to.")
    info("")

    for role in roles:
        targets = [r for r in roles if r != role]
        selected = ask_checkbox(f"{role} can route to:", targets) or []
        if selected:
            edges[role] = selected

    return edges


def _print_matrix(roles: list[str], edges: dict[str, list[str]]) -> None:
    """Print a Rich table showing the routing matrix."""
    from arcium.tui.styles import console

    table = Table(
        title="Routing matrix",
        show_header=True,
        header_style="arcium.subtitle",
        border_style="arcium.muted",
        padding=(0, 1),
    )

    table.add_column("FROM \\ TO", style="arcium.muted", min_width=16)
    for role in roles:
        table.add_column(role[:12], justify="center", min_width=8)

    for from_role in roles:
        row = [f"[arcium.teal]{from_role[:16]}[/]"]
        for to_role in roles:
            if from_role == to_role:
                row.append("[arcium.muted]—[/]")
            elif to_role in edges.get(from_role, []):
                row.append("[arcium.success]✓[/]")
            else:
                row.append("[arcium.muted]·[/]")
        table.add_row(*row)

    console.print(table)


def _edges_to_graph_nodes(
    roles: list[str],
    edges: dict[str, list[str]],
) -> list[dict]:
    """Convert edge dict to COHORT.md graph node format."""
    nodes = []
    for i, role in enumerate(roles):
        valid_routes = edges.get(role, [])
        default_next = valid_routes[0] if valid_routes else None
        terminal = len(valid_routes) == 0

        node: dict = {
            "id": role,
            "role": role,
            "default_next": default_next,
            "valid_routes": valid_routes,
        }
        if terminal:
            node["terminal"] = True
        if i == len(roles) - 2:
            # Second-to-last node (typically critic) gets escalation on max iterations
            node["on_max_iterations"] = "escalate"

        nodes.append(node)
    return nodes
