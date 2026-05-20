"""v0.3: Local Kamailio start/stop control and variable state diff table."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KamailioInstance:
    name: str
    config_path: str
    ctl_socket: str = ""
    pid_file: str = ""
    running: bool = False


class KamailioController:
    """Control local Kamailio instances from notebook cells."""

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or self._detect_project_root()
        self.instances: dict[str, KamailioInstance] = {}
        self._detect_instances()

    def _detect_project_root(self) -> str:
        """Detect kamailio project root."""
        cwd = os.getcwd()
        # Walk up to find kamailio-start.sh
        path = cwd
        for _ in range(10):
            if os.path.exists(os.path.join(path, "kamailio-start.sh")):
                return path
            parent = os.path.dirname(path)
            if parent == path:
                break
            path = parent
        return cwd

    def _detect_instances(self):
        """Detect available Kamailio instances from the project."""
        start_script = os.path.join(self.project_root, "kamailio-start.sh")
        stop_script = os.path.join(self.project_root, "kamailio-stop.sh")

        if not os.path.exists(start_script):
            return

        # Known instance patterns from the project
        default_instances = {
            "lb": KamailioInstance(
                name="lb",
                config_path="etc/local-lb.cfg",
                ctl_socket="run/kamailio_lb_ctl",
                pid_file="run/kamailio_lb.pid",
            ),
            "node1": KamailioInstance(
                name="node1",
                config_path="etc/local-node1.cfg",
                ctl_socket="run/kamailio_node1_ctl",
                pid_file="run/kamailio_node1.pid",
            ),
            "node2": KamailioInstance(
                name="node2",
                config_path="etc/local-node2.cfg",
                ctl_socket="run/kamailio_node2_ctl",
                pid_file="run/kamailio_node2.pid",
            ),
        }

        for name, inst in default_instances.items():
            inst.config_path = os.path.join(self.project_root, inst.config_path)
            inst.ctl_socket = os.path.join(self.project_root, inst.ctl_socket)
            inst.pid_file = os.path.join(self.project_root, inst.pid_file)
            self.instances[name] = inst

    def start(self, instance: str = "all") -> dict:
        """Start a Kamailio instance or all instances."""
        script = os.path.join(self.project_root, "kamailio-start.sh")
        if not os.path.exists(script):
            return {"error": f"kamailio-start.sh not found at {script}"}

        try:
            result = subprocess.run(
                ["bash", script],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
            )
            self._refresh_status()
            return {
                "returncode": result.returncode,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Start command timed out (30s)"}
        except Exception as e:
            return {"error": str(e)}

    def stop(self, instance: str = "all") -> dict:
        """Stop a Kamailio instance or all instances."""
        script = os.path.join(self.project_root, "kamailio-stop.sh")
        if not os.path.exists(script):
            return {"error": f"kamailio-stop.sh not found at {script}"}

        cmd = ["bash", script]
        if instance != "all":
            cmd.append(instance)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
            )
            self._refresh_status()
            return {
                "returncode": result.returncode,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.returncode != 0 else None,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Stop command timed out (30s)"}
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> dict[str, bool]:
        """Check status of all instances."""
        self._refresh_status()
        return {name: inst.running for name, inst in self.instances.items()}

    def _refresh_status(self):
        """Update running status by checking pid files."""
        for name, inst in self.instances.items():
            if inst.pid_file and os.path.exists(inst.pid_file):
                try:
                    with open(inst.pid_file) as f:
                        pid = int(f.read().strip())
                    # Check if process is alive
                    os.kill(pid, 0)
                    inst.running = True
                except (ValueError, ProcessLookupError, PermissionError):
                    inst.running = False
            else:
                inst.running = False

    def format_status(self) -> str:
        """Format status as a readable table."""
        self._refresh_status()
        lines = ["┌──────────┬─────────┬─────────────────────────┐",
                 "│ Instance │ Status  │ Config                  │",
                 "├──────────┼─────────┼─────────────────────────┤"]

        for name, inst in self.instances.items():
            status = "● Running" if inst.running else "○ Stopped"
            cfg = os.path.basename(inst.config_path)
            lines.append(f"│ {name:<8} │ {status:<7} │ {cfg:<23} │")

        lines.append("└──────────┴─────────┴─────────────────────────┘")
        return "\n".join(lines)


@dataclass
class VarSnapshot:
    """Snapshot of variable state at a point in time."""
    variables: dict[str, str]
    timestamp: str = ""


class VarDiffTable:
    """Compare variable state before/after execution and render as diff table."""

    @staticmethod
    def snapshot(vars_dump: dict[str, str], label: str = "") -> VarSnapshot:
        import datetime
        return VarSnapshot(
            variables=dict(vars_dump),
            timestamp=label or datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3],
        )

    @staticmethod
    def diff(before: VarSnapshot, after: VarSnapshot) -> dict[str, tuple[str, str, str]]:
        """Compute diff between two snapshots.
        Returns {var_name: (before_val, after_val, change_type)}
        change_type: "added", "removed", "changed", "unchanged"
        """
        result = {}
        all_keys = set(before.variables.keys()) | set(after.variables.keys())

        for key in sorted(all_keys):
            before_val = before.variables.get(key, None)
            after_val = after.variables.get(key, None)

            if before_val is None and after_val is not None:
                result[key] = ("", after_val, "added")
            elif before_val is not None and after_val is None:
                result[key] = (before_val, "", "removed")
            elif before_val != after_val:
                result[key] = (before_val, after_val, "changed")
            else:
                result[key] = (before_val, after_val, "unchanged")

        return result

    @staticmethod
    def render_text(diff: dict[str, tuple[str, str, str]]) -> str:
        """Render diff as text table."""
        lines = [f"{'Variable':<20} {'Before':<25} {'After':<25} {'Change':<10}",
                 "-" * 80]

        for key, (before, after, change) in diff.items():
            if change == "unchanged":
                continue
            marker = {"added": "+", "removed": "-", "changed": "~"}[change]
            lines.append(f"{marker} {key:<18} {before:<25} {after:<25} {change:<10}")

        unchanged = sum(1 for _, (_, _, c) in diff.items() if c == "unchanged")
        lines.append(f"\n({unchanged} variables unchanged)")
        return "\n".join(lines)

    @staticmethod
    def render_html(diff: dict[str, tuple[str, str, str]]) -> str:
        """Render diff as colored HTML table."""
        html_parts = [
            '<table style="border-collapse: collapse; font-family: monospace; font-size: 13px;">',
            '<tr style="background: #f0f0f0;">',
            '<th style="padding: 6px 12px; text-align: left;">Variable</th>',
            '<th style="padding: 6px 12px; text-align: left;">Before</th>',
            '<th style="padding: 6px 12px; text-align: left;">After</th>',
            '<th style="padding: 6px 12px; text-align: left;">Change</th>',
            '</tr>',
        ]

        for key, (before, after, change) in diff.items():
            if change == "unchanged":
                continue

            colors = {
                "added": ("#d4edda", "#155724"),
                "removed": ("#f8d7da", "#721c24"),
                "changed": ("#fff3cd", "#856404"),
            }
            bg, fg = colors.get(change, ("#ffffff", "#000000"))

            html_parts.append(
                f'<tr style="background: {bg}; color: {fg};">'
                f'<td style="padding: 4px 12px; border-bottom: 1px solid #ddd;">{key}</td>'
                f'<td style="padding: 4px 12px; border-bottom: 1px solid #ddd;">{before or "—"}</td>'
                f'<td style="padding: 4px 12px; border-bottom: 1px solid #ddd;">{after or "—"}</td>'
                f'<td style="padding: 4px 12px; border-bottom: 1px solid #ddd;">{change}</td>'
                f'</tr>'
            )

        html_parts.append('</table>')
        return "".join(html_parts)
