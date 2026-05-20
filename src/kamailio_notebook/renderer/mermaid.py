"""Mermaid diagram renderer for SIP message flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SIPFlowStep:
    from_entity: str
    to_entity: str
    message: str
    note: str = ""


class MermaidRenderer:
    """Generate Mermaid sequence diagrams from SIP message flows."""

    def __init__(self):
        self.steps: list[SIPFlowStep] = []
        self.entities: list[str] = []
        self.entity_aliases: dict[str, str] = {}

    def clear(self):
        self.steps.clear()
        self.entities.clear()
        self.entity_aliases.clear()

    def add_entity(self, name: str, alias: Optional[str] = None):
        if name in self.entity_aliases:
            return
        if not alias:
            alias = name.replace(" ", "_").replace("-", "_")
            alias = alias[:12]
        self.entities.append(name)
        self.entity_aliases[name] = alias

    def add_step(self, from_entity: str, to_entity: str, message: str, note: str = ""):
        self.add_entity(from_entity)
        self.add_entity(to_entity)
        self.steps.append(SIPFlowStep(from_entity, to_entity, message, note))

    def render(self) -> str:
        if not self.steps:
            return ""

        lines = ["sequenceDiagram"]

        # Add entity declarations
        for entity in self.entities:
            alias = self.entity_aliases[entity]
            lines.append(f"    participant {alias} as {entity}")

        # Add message arrows
        for step in self.steps:
            from_alias = self.entity_aliases[step.from_entity]
            to_alias = self.entity_aliases[step.to_entity]

            # Color code by message type
            msg = step.message
            if msg.startswith("1"):
                lines.append(f"    {from_alias}->>{to_alias}: {msg} (provisional)")
            elif msg.startswith("2"):
                lines.append(f"    {to_alias}-->>{from_alias}: {msg} (success)")
            elif msg.startswith("3"):
                lines.append(f"    {to_alias}-->>{from_alias}: {msg} (redirect)")
            elif msg.startswith("4") or msg.startswith("5") or msg.startswith("6"):
                lines.append(f"    {to_alias}--x{from_alias}: {msg} (error)")
            else:
                lines.append(f"    {from_alias}->>{to_alias}: {msg}")

            if step.note:
                lines.append(f"    Note over {from_alias},{to_alias}: {step.note}")

        return "\n".join(lines)

    def render_html(self) -> str:
        """Render as an HTML block with mermaid div for Jupyter display."""
        mermaid_code = self.render()
        if not mermaid_code:
            return ""

        return f"""<div class="mermaid">
{mermaid_code}
</div>
<script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true }});
    mermaid.run();
</script>"""


def build_flow_from_trace(trace: list[str], entities: Optional[list[str]] = None) -> MermaidRenderer:
    """Build a SIP flow diagram from execution trace entries."""
    renderer = MermaidRenderer()

    if not entities:
        entities = ["UAC", "Kamailio", "UAS"]

    for entity in entities:
        renderer.add_entity(entity)

    prev = entities[0] if entities else "UAC"

    for entry in trace:
        if entry.startswith("send_reply"):
            msg = entry.replace("send_reply(", "").rstrip(")")
            renderer.add_step("Kamailio", prev, f"SIP {msg}")
        elif entry.startswith("assign:"):
            parts = entry.replace("assign: ", "").split(" = ")
            if len(parts) >= 2:
                renderer.add_step("Kamailio", "Kamailio", f"set {parts[0]} = {parts[1]}")
        elif entry.startswith("route("):
            route_name = entry
            renderer.add_step("Kamailio", "Kamailio", route_name)
        elif entry.startswith("xlog:"):
            pass
        else:
            renderer.add_step(prev, "Kamailio", entry)

    return renderer
