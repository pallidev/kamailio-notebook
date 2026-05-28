"""v0.2: Route block tracing and if/else branch visualization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RouteTraceStep:
    route_name: str
    line: int
    statement: str
    result: Optional[str] = None
    branch_taken: Optional[str] = None  # "if-true", "if-false", "else"


@dataclass
class BranchNode:
    condition: str
    result: bool
    if_body_trace: list[RouteTraceStep] = field(default_factory=list)
    else_body_trace: list[RouteTraceStep] = field(default_factory=list)


class RouteTracer:
    """Traces execution of route[] blocks step by step."""

    def __init__(self):
        self.steps: list[RouteTraceStep] = []
        self.branches: list[BranchNode] = []
        self.current_route: Optional[str] = None
        self.indent_level: int = 0

    def start_route(self, name: str):
        self.current_route = name
        self.steps.append(RouteTraceStep(
            route_name=name,
            line=0,
            statement=f"route[{name}] {{",
        ))
        self.indent_level += 1

    def end_route(self):
        if self.current_route:
            self.steps.append(RouteTraceStep(
                route_name=self.current_route,
                line=0,
                statement="}",
            ))
            self.current_route = None
        self.indent_level = max(0, self.indent_level - 1)

    def trace_statement(self, statement: str, line: int = 0, result: str = ""):
        self.steps.append(RouteTraceStep(
            route_name=self.current_route or "",
            line=line,
            statement=statement,
            result=result,
        ))

    def trace_branch(self, condition: str, result: bool,
                      if_steps: list[RouteTraceStep] = None,
                      else_steps: list[RouteTraceStep] = None):
        branch = BranchNode(
            condition=condition,
            result=result,
            if_body_trace=if_steps or [],
            else_body_trace=else_steps or [],
        )
        self.branches.append(branch)

    def render_text(self) -> str:
        """Render trace as indented text."""
        lines = []
        for step in self.steps:
            indent = "  " * self._effective_indent(step)
            line = f"{indent}{step.statement}"
            if step.result:
                line += f"  → {step.result}"
            lines.append(line)

        for branch in self.branches:
            result_str = "TRUE" if branch.result else "FALSE"
            lines.append(f"  if ({branch.condition}) → {result_str}")
            for step in branch.if_body_trace:
                lines.append(f"    ✓ {step.statement}")
            for step in branch.else_body_trace:
                lines.append(f"    ✗ else: {step.statement}")

        return "\n".join(lines)

    def render_html(self) -> str:
        """Render trace as colored HTML for notebook display."""
        html_parts = ['<div style="font-family: monospace; font-size: 13px; line-height: 1.6;">']

        for step in self.steps:
            indent = self._effective_indent(step) * 24
            style = ""

            if step.result and "error" in step.result.lower():
                style = 'color: #e74c3c;'
            elif step.result and "true" in step.result.lower():
                style = 'color: #27ae60;'
            elif step.result and "false" in step.result.lower():
                style = 'color: #e67e22;'

            result_span = f' <span style="color: #7f8c8d;">&rarr; {step.result}</span>' if step.result else ""
            html_parts.append(
                f'<div style="margin-left: {indent}px; {style}">'
                f'{_escape_html(step.statement)}'
                f'{result_span}'
                f'</div>'
            )

        for branch in self.branches:
            result_color = "#27ae60" if branch.result else "#e67e22"
            result_text = "✓ TRUE" if branch.result else "✗ FALSE"
            html_parts.append(
                f'<div style="margin-top: 8px; padding: 4px 8px; '
                f'background: #f8f9fa; border-left: 3px solid {result_color};">'
                f'<span style="color: {result_color};">if ({branch.condition}) → {result_text}</span></div>'
            )

            for step in branch.if_body_trace:
                html_parts.append(
                    f'<div style="margin-left: 24px; color: #27ae60;">'
                    f'✓ {_escape_html(step.statement)}</div>'
                )
            for step in branch.else_body_trace:
                html_parts.append(
                    f'<div style="margin-left: 24px; color: #e67e22;">'
                    f'↳ {_escape_html(step.statement)}</div>'
                )

        html_parts.append('</div>')
        return "".join(html_parts)

    def render_mermaid_flowchart(self) -> str:
        """Render if/else branches as a Mermaid flowchart."""
        if not self.branches:
            return ""

        lines = ["flowchart TD"]
        node_id = 0

        for branch in self.branches:
            cond_id = f"c{node_id}"
            node_id += 1
            cond_text = branch.condition.replace('"', "'")
            result_text = "TRUE" if branch.result else "FALSE"

            lines.append(f"    {cond_id}[\"if ({cond_text})\"]")

            if branch.result and branch.if_body_trace:
                yes_id = f"y{node_id}"
                node_id += 1
                yes_stmts = "<br>".join(s.statement for s in branch.if_body_trace)
                lines.append(f"    {cond_id} -->|YES| {yes_id}[\"{yes_stmts}\"]")
                lines.append(f"    style {yes_id} fill:#d4edda,stroke:#27ae60")
            elif not branch.result and branch.else_body_trace:
                no_id = f"n{node_id}"
                node_id += 1
                no_stmts = "<br>".join(s.statement for s in branch.else_body_trace)
                lines.append(f"    {cond_id} -->|NO| {no_id}[\"{no_stmts}\"]")
                lines.append(f"    style {no_id} fill:#fff3cd,stroke:#e67e22")

            lines.append(f"    style {cond_id} fill:#e3f2fd,stroke:#2196f3")

        return "\n".join(lines)

    def _effective_indent(self, step: RouteTraceStep) -> int:
        if step.statement in ("}", "}") or step.statement.startswith("}"):
            return max(0, self.indent_level - 1)
        if step.statement.startswith("route["):
            return 0
        return self.indent_level

    def clear(self):
        self.steps.clear()
        self.branches.clear()
        self.current_route = None
        self.indent_level = 0


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
