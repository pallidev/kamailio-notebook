"""Variable store for Kamailio pseudo-variables."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class VarType(Enum):
    STRING = "string"
    INTEGER = "integer"
    NULL = "null"


@dataclass
class VarValue:
    type: VarType
    value: Any

    def __str__(self) -> str:
        if self.type == VarType.NULL:
            return "<null>"
        if self.type == VarType.INTEGER:
            return str(self.value)
        return f'"{self.value}"'

    def to_int(self) -> int:
        if self.type == VarType.INTEGER:
            return self.value
        if self.type == VarType.STRING:
            try:
                return int(self.value)
            except (ValueError, TypeError):
                return 0
        return 0

    def to_str(self) -> str:
        if self.type == VarType.NULL:
            return ""
        return str(self.value)


class VariableStore:
    """Manages Kamailio pseudo-variables: $var, $avp, $hdr, and SIP message vars."""

    def __init__(self):
        # Script variables ($var(name))
        self.script_vars: dict[str, VarValue] = {}

        # AVPs ($avp(name))
        self.avps: dict[str, list[VarValue]] = {}

        # Header variables ($hdr(name))
        self.headers: dict[str, VarValue] = {}

        # SIP message pseudo-variables
        self.msg_vars: dict[str, VarValue] = {}

        # Execution log for tracking changes
        self.log: list[str] = []

    def get(self, name: str) -> VarValue:
        """Get a variable value by full name like $var(x), $avp(src), $ru, $fu."""
        name = name.strip()

        if name.startswith("$var(") or name.startswith("$(var("):
            return self._get_script_var(name)
        if name.startswith("$avp(") or name.startswith("$(avp("):
            return self._get_avp(name)
        if name.startswith("$hdr(") or name.startswith("$(hdr("):
            return self._get_header(name)

        # Direct message variables
        msg_var_map = {
            "$ru": "$ru", "$fu": "$fu", "$tu": "$tu",
            "$ci": "$ci", "$cs": "$cs",
            "$si": "$si", "$sp": "$sp", "$Ri": "$Ri", "$Rp": "$Rp",
            "$rm": "$rm", "$rp": "$rp",
            "$ua": "$ua", "$cl": "$cl", "$ct": "$ct",
        }
        if name in msg_var_map:
            return self.msg_vars.get(name, VarValue(VarType.NULL, None))

        return VarValue(VarType.NULL, None)

    def set(self, name: str, value: VarValue):
        """Set a variable value."""
        name = name.strip()

        if name.startswith("$var(") or name.startswith("$(var("):
            key = self._extract_key(name)
            old = self.script_vars.get(key, VarValue(VarType.NULL, None))
            self.script_vars[key] = value
            self.log.append(f"$var({key}): {old} → {value}")
            return

        if name.startswith("$avp(") or name.startswith("$(avp("):
            key = self._extract_key(name)
            if key not in self.avps:
                self.avps[key] = []
            self.avps[key].append(value)
            self.log.append(f"$avp({key}): appended {value}")
            return

        # Direct message variable assignment
        if name.startswith("$"):
            old = self.msg_vars.get(name, VarValue(VarType.NULL, None))
            self.msg_vars[name] = value
            self.log.append(f"{name}: {old} → {value}")
            return

    def init_from_message(self, msg):
        """Initialize message-level variables from a SIPMessage."""
        from .sip_message import SIPMessage

        if not isinstance(msg, SIPMessage):
            return

        self.msg_vars = {
            "$ru": VarValue(VarType.STRING, msg.request_uri),
            "$fu": VarValue(VarType.STRING, msg.from_uri),
            "$tu": VarValue(VarType.STRING, msg.to_uri),
            "$ci": VarValue(VarType.STRING, msg.call_id),
            "$cs": VarValue(VarType.STRING, msg.cseq),
            "$rm": VarValue(VarType.STRING, msg.method),
            "$si": VarValue(VarType.STRING, msg.src_ip),
            "$sp": VarValue(VarType.INTEGER, msg.src_port),
            "$Ri": VarValue(VarType.STRING, msg.dst_ip),
            "$Rp": VarValue(VarType.INTEGER, msg.dst_port),
            "$ua": VarValue(VarType.STRING, ""),
            "$cl": VarValue(VarType.STRING, msg.content_length),
            "$ct": VarValue(VarType.STRING, msg.contact),
        }

        if msg.from_tag:
            self.msg_vars["$ft"] = VarValue(VarType.STRING, msg.from_tag)
        if msg.to_tag:
            self.msg_vars["$tt"] = VarValue(VarType.STRING, msg.to_tag)

    def dump(self) -> dict[str, str]:
        """Return all variables as a string dict for display."""
        result = {}

        for key, val in sorted(self.msg_vars.items()):
            result[key] = f"{val}"

        for key, val in sorted(self.script_vars.items()):
            result[f"$var({key})"] = f"{val}"

        for key, vals in sorted(self.avps.items()):
            for i, val in enumerate(vals):
                result[f"$avp({key})[{i}]"] = f"{val}"

        for key, val in sorted(self.headers.items()):
            result[f"$hdr({key})"] = f"{val}"

        return result

    def _get_script_var(self, name: str) -> VarValue:
        key = self._extract_key(name)
        return self.script_vars.get(key, VarValue(VarType.NULL, None))

    def _get_avp(self, name: str) -> VarValue:
        key = self._extract_key(name)
        vals = self.avps.get(key, [])
        return vals[-1] if vals else VarValue(VarType.NULL, None)

    def _get_header(self, name: str) -> VarValue:
        key = self._extract_key(name)
        return self.headers.get(key, VarValue(VarType.NULL, None))

    def _extract_key(self, name: str) -> str:
        """Extract key from $var(key) or $(var(key))."""
        match = re.search(r'\(([^)]+)\)', name)
        return match.group(1) if match else name
