"""Kamailio kamcmd integration for live server queries."""

from __future__ import annotations

import json
import subprocess
import shutil
from dataclasses import dataclass
from typing import Optional


@dataclass
class KamctlConfig:
    kamcmd_path: str = ""
    ctl_socket: str = ""

    @classmethod
    def auto_detect(cls) -> KamctlConfig:
        """Try to find kamcmd and ctl socket automatically."""
        cfg = cls()

        # Try to find kamcmd
        kamcmd = shutil.which("kamcmd")
        if kamcmd:
            cfg.kamcmd_path = kamcmd
        else:
            # Check common paths
            for path in [
                "/usr/sbin/kamcmd",
                "/usr/local/sbin/kamcmd",
                "/opt/kamailio/sbin/kamcmd",
            ]:
                import os
                if os.path.exists(path):
                    cfg.kamcmd_path = path
                    break

        # Try to find ctl socket
        for socket_path in [
            "run/kamailio_lb_ctl",
            "run/kamailio_node1_ctl",
            "/run/kamailio/kamailio_ctl",
            "/var/run/kamailio/kamailio_ctl",
            "/tmp/kamailio_ctl",
        ]:
            import os
            if os.path.exists(socket_path):
                cfg.ctl_socket = socket_path
                break

        return cfg


class KamcmdRunner:
    """Execute kamcmd commands against a running Kamailio instance."""

    def __init__(self, config: Optional[KamctlConfig] = None):
        self.config = config or KamctlConfig.auto_detect()

    @property
    def available(self) -> bool:
        return bool(self.config.kamcmd_path)

    def run(self, command: str, socket: Optional[str] = None) -> dict:
        """Run a kamcmd command and return the result."""
        if not self.config.kamcmd_path:
            return {
                "error": "kamcmd not found. Install Kamailio or set kamcmd_path.",
                "output": None,
            }

        socket = socket or self.config.ctl_socket
        cmd = [self.config.kamcmd_path]
        if socket:
            cmd.extend(["-s", socket])
        cmd.extend(command.split())

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "output": result.stdout.strip() if result.returncode == 0 else result.stderr.strip(),
            }
        except FileNotFoundError:
            return {"error": f"kamcmd not found at {self.config.kamcmd_path}", "output": None}
        except subprocess.TimeoutExpired:
            return {"error": "kamcmd command timed out (10s)", "output": None}
        except Exception as e:
            return {"error": str(e), "output": None}

    def dispatcher_list(self, socket: Optional[str] = None) -> dict:
        return self.run("dispatcher.list", socket)

    def usrloc_dump(self, socket: Optional[str] = None) -> dict:
        return self.run("ul.dump", socket)

    def dialog_list(self, socket: Optional[str] = None) -> dict:
        return self.run("dlg.list", socket)

    def stats(self, socket: Optional[str] = None) -> dict:
        return self.run("stats.getrpl", socket)

    def ping(self, socket: Optional[str] = None) -> dict:
        return self.run("core.ping", socket)

    def uptime(self, socket: Optional[str] = None) -> dict:
        return self.run("core.uptime", socket)

    def list_sockets(self, socket: Optional[str] = None) -> dict:
        return self.run("core.sockets_list", socket)
