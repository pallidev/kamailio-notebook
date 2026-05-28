"""Kamailio CFG Jupyter Notebook Kernel — ipykernel native."""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from ipykernel.kernelbase import Kernel

from .cfg_executor import CfgExecutor
from .cfg_tracer import RouteTracer
from .kamcmd import KamcmdRunner
from .kamailio_control import KamailioController, VarDiffTable, VarSnapshot
from .sip_message import SIPMessage, VALID_METHODS
from .variables import VarValue, VarType, VariableStore
from .renderer.mermaid import MermaidRenderer


class KamailioKernel(Kernel):
    implementation = "Kamailio CFG"
    implementation_version = "0.3.0"
    language = "kamailio-cfg"
    language_version = "6.1"
    language_info = {
        "name": "kamailio-cfg",
        "mimetype": "text/x-kamailio-cfg",
        "file_extension": ".cfg",
        "pygments_lexer": "kamailio-cfg",
        "codemirror_mode": "shell",
    }
    banner = "Kamailio CFG Notebook Kernel v0.3.0"

    # VS Code Jupyter extension only sends execute_request for kernels
    # whose language_info.name it recognizes. Report as "python" so VS Code
    # routes cell execution through our kernel, while keeping the display
    # name as "Kamailio CFG" for the kernel picker.
    @property
    def kernel_info(self):
        info = super().kernel_info
        info["language_info"] = {
            "name": "python",
            "version": "3",
            "mimetype": "text/x-kamailio-cfg",
            "file_extension": ".cfg",
            "pygments_lexer": "kamailio-cfg",
            "codemirror_mode": "shell",
        }
        info["supported_features"] = []
        return info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.vars = VariableStore()
        self.message: Optional[SIPMessage] = None
        self.executor = CfgExecutor(self.vars)
        self.kamcmd = KamcmdRunner()
        self.mermaid = MermaidRenderer()
        self.tracer = RouteTracer()
        self.controller = KamailioController()
        self._var_snapshot_before: Optional[VarSnapshot] = None

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def do_execute(
        self,
        code,
        silent,
        store_history=True,
        user_expressions=None,
        allow_stdin=False,
    ):
        if not code.strip():
            return {"status": "ok", "execution_count": self.execution_count, "payload": [], "user_expressions": {}}

        lines = code.strip().split("\n")

        # Handle magics first
        if lines[0].startswith("%%sip"):
            self._handle_sip_magic(code)
            return self._ok()

        if lines[0].startswith("%%kamcmd"):
            self._handle_kamcmd_magic(code)
            return self._ok()

        if lines[0].startswith("%%vars"):
            self._handle_vars_magic()
            return self._ok()

        if lines[0].startswith("%%flow"):
            self._handle_flow_magic()
            return self._ok()

        if lines[0].startswith("%%reset"):
            self._handle_reset_magic()
            return self._ok()

        if lines[0].startswith("%%trace"):
            self._handle_trace_magic(code)
            return self._ok()

        if lines[0].startswith("%%diff"):
            self._handle_diff_magic()
            return self._ok()

        if lines[0].startswith("%%kamailio"):
            self._handle_kamailio_magic(code)
            return self._ok()

        if lines[0].startswith("%%help"):
            topic = lines[0].replace("%%help", "").strip()
            self._handle_help_magic(topic)
            return self._ok()

        # Take snapshot before execution
        if self._var_snapshot_before is not None:
            self._var_snapshot_before = VarDiffTable.snapshot(self.vars.dump(), "after")
        self._var_snapshot_before = VarDiffTable.snapshot(self.vars.dump(), "before")

        # Execute cfg code
        result = self.executor.execute_cell(code)

        if not silent:
            for line in result.output:
                self._print(line)

            if result.errors:
                self._print_err("\n".join(result.errors))

            if result.branches:
                self.tracer.clear()
                for branch in result.branches:
                    self._print(f"  \U0001f500 {branch}")

            if result.variables_changed:
                self._print("")
                self._print("Variables changed:")
                for var, (old, new) in result.variables_changed.items():
                    self._print(f"  {var}: {old} → {new}")

        return self._ok()

    # ------------------------------------------------------------------
    # Tab completion
    # ------------------------------------------------------------------

    def do_complete(self, code, cursor_pos):
        text = code[:cursor_pos]
        match = re.search(r'[\w.${}%]+$', text)
        if not match:
            return {"status": "ok", "matches": [], "cursor_start": cursor_pos, "cursor_end": cursor_pos}

        fragment = match.group()
        start = match.start()

        candidates = _get_all_completions()
        matches = sorted(c for c in candidates if c.startswith(fragment))

        return {"status": "ok", "matches": matches, "cursor_start": start, "cursor_end": cursor_pos}

    # ------------------------------------------------------------------
    # Help / inspect (Shift+Tab)
    # ------------------------------------------------------------------

    def do_inspect(self, code, cursor_pos, detail_level=0):
        match = re.search(r'[\w.${}%]+', code[:cursor_pos][::-1])
        if match:
            name = match.group()[::-1]
        else:
            name = code.strip()

        help_text = _get_help(name)
        if help_text:
            return {"status": "ok", "found": True, "data": {"text/plain": help_text}}
        return {"status": "ok", "found": False}

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _ok(self):
        return {
            "status": "ok",
            "execution_count": self.execution_count,
            "payload": [],
            "user_expressions": {},
        }

    def _print(self, text):
        self.send_response(self.iopub_socket, "stream", {"name": "stdout", "text": text + "\n"})

    def _print_err(self, text):
        self.send_response(self.iopub_socket, "stream", {"name": "stderr", "text": text + "\n"})

    def _show(self, data):
        self.send_response(self.iopub_socket, "display_data", {"data": data, "metadata": {}})

    # ------------------------------------------------------------------
    # Magic handlers
    # ------------------------------------------------------------------

    def _handle_sip_magic(self, code: str):
        lines = code.strip().split("\n")
        first_line = lines[0]
        rest = "\n".join(lines[1:])

        method_match = re.match(r'%%sip\s+(\w+)', first_line)
        if not method_match:
            self._print_err("Usage: %%sip INVITE|REGISTER|BYE ...")
            return

        method = method_match.group(1).upper()
        if method not in VALID_METHODS:
            self._print_err(f"Unknown SIP method: {method}")
            return

        self.message = SIPMessage.from_raw(method, rest)
        self.vars.init_from_message(self.message)

        self._print(f"Mock {method} message created:")
        self._print("")
        self._print(self.message.format_display())
        self._print("")
        self._print("Variables initialized:")
        for key, val in self.vars.dump().items():
            if key.startswith("$") and not key.startswith("$var") and not key.startswith("$avp"):
                self._print(f"  {key} = {val}")

    def _handle_kamcmd_magic(self, code: str):
        lines = code.strip().split("\n")
        command = lines[0].replace("%%kamcmd", "").strip()
        socket = None

        if len(lines) > 1:
            for line in lines[1:]:
                if line.startswith("--socket"):
                    socket = line.split("=", 1)[1].strip() if "=" in line else None
                else:
                    if command:
                        command += " " + line
                    else:
                        command = line

        if not command:
            self._print_err("Usage: %%kamcmd <command> [--socket=/path/to/ctl]")
            return

        result = self.kamcmd.run(command, socket)
        if "error" in result:
            self._print_err(f"Error: {result['error']}")
            return

        self._print(result.get("output", "(no output)"))

    def _handle_vars_magic(self):
        dump = self.vars.dump()
        if not dump:
            self._print("(no variables set)")
            return

        lines = [f"{'Variable':<20} {'Type':<10} {'Value'}", "-" * 60]
        for key, val in sorted(dump.items()):
            v = self.vars.get(key)
            type_str = v.type.value if v.type != VarType.NULL else ""
            lines.append(f"{key:<20} {type_str:<10} {val}")

        self._print("\n".join(lines))

    def _handle_flow_magic(self):
        mermaid_code = self.mermaid.render()
        if not mermaid_code:
            self._print("(no flow recorded)")
            return
        self._print(f"```mermaid\n{mermaid_code}\n```")

    def _handle_reset_magic(self):
        self.vars = VariableStore()
        self.message = None
        self.executor = CfgExecutor(self.vars)
        self.mermaid = MermaidRenderer()
        self.tracer.clear()
        self._var_snapshot_before = None
        self._print("All state cleared.")

    def _handle_trace_magic(self, code: str):
        lines = code.strip().split("\n")
        cfg_code = "\n".join(lines[1:])

        if not cfg_code.strip():
            text = self.tracer.render_text()
            self._print(text or "(no trace recorded)")
            return

        self.tracer.clear()
        result = self.executor.execute_cell(cfg_code)

        for output in result.output:
            self.tracer.trace_statement(output)

        for branch in result.branches:
            self.tracer.trace_branch(
                condition=branch.split("if(")[1].split(")")[0] if "if(" in branch else branch,
                result="TRUE" in branch,
            )

        html = self.tracer.render_html()
        if html:
            self._show({"text/html": html})

        flowchart = self.tracer.render_mermaid_flowchart()
        if flowchart:
            self._show({"text/plain": flowchart, "text/x-mermaid": flowchart})

    def _handle_diff_magic(self):
        if self._var_snapshot_before is None:
            self._print("No snapshot available. Execute a cell first.")
            return

        after_snapshot = VarDiffTable.snapshot(self.vars.dump(), "after")
        diff = VarDiffTable.diff(self._var_snapshot_before, after_snapshot)

        has_changes = any(c != "unchanged" for _, (_, _, c) in diff.items())
        if not has_changes:
            self._print("No variable changes detected.")
            return

        self._print(VarDiffTable.render_text(diff))
        self._show({"text/html": VarDiffTable.render_html(diff)})

    def _handle_kamailio_magic(self, code: str):
        lines = code.strip().split("\n")
        command = lines[0].replace("%%kamailio", "").strip()

        if command in ("status", ""):
            self._print(self.controller.format_status())
            return

        if command == "start":
            instance = lines[1].strip() if len(lines) > 1 else "all"
            result = self.controller.start(instance)
            if "error" in result:
                self._print_err(result["error"])
            else:
                self._print(result.get("output", "Started."))
                self._print("")
                self._print(self.controller.format_status())

        elif command == "stop":
            instance = lines[1].strip() if len(lines) > 1 else "all"
            result = self.controller.stop(instance)
            if "error" in result:
                self._print_err(result["error"])
            else:
                self._print(result.get("output", "Stopped."))
                self._print("")
                self._print(self.controller.format_status())

        else:
            self._print_err(f"Unknown kamailio command: {command}")
            self._print_err("Available: %%kamailio status|start|stop [instance]")

    def _handle_help_magic(self, topic: str):
        if topic:
            help_text = _get_help(topic)
            self._print(help_text or f"No help available for: {topic}")
        else:
            self._print(_get_general_help())


# ------------------------------------------------------------------
# Help database
# ------------------------------------------------------------------

def _get_help(name: str) -> Optional[str]:
    help_db = {
        "$var": (
            "$var(name) — Script variable\n"
            "  Scope: per-process, not shared\n"
            "  Types: string or integer (auto-determined)\n"
            "  Example: $var(count) = 10;\n"
            "           $var(uri) = \"sip:1001@localhost\";"
        ),
        "$avp": (
            "$avp(name) — Attribute-Value Pair\n"
            "  Scope: per-transaction (shared across processes)\n"
            "  Can store multiple values (stack-like)\n"
            "  Example: $avp(caller) = \"1001\";\n"
            "           $avp(caller) = \"1002\";  # pushes, doesn't replace"
        ),
        "$ru": (
            "$ru — Request URI\n"
            "  The R-URI of the current SIP request.\n"
            "  Read/write. Changing $ru affects where the request is sent.\n"
            "  Example: $ru = \"sip:1002@10.0.0.1:5060\";\n"
            "  Transform: $(ru{uri.user}) → \"1002\""
        ),
        "$fu": (
            "$fu — From URI\n"
            "  The URI in the From header.\n"
            "  Read/write.\n"
            "  Transform: $(fu{uri.user}) → extracts the user part"
        ),
        "$tu": (
            "$tu — To URI\n"
            "  The URI in the To header.\n"
            "  Read/write."
        ),
        "ds_select_dst": (
            "ds_select_dst(set_id, alg) — Dispatcher: select destination\n"
            "  set_id: dispatcher set number\n"
            "  alg: algorithm (0=round-robin, 2=hash(callid), 4=first, ...)\n"
            "  Sets $du to the selected destination.\n"
            "  Example: ds_select_dst(\"1\", \"4\");"
        ),
        "rtpengine_manage": (
            "rtpengine_manage(...) — Manage RTP relay session\n"
            "  Handles offer/answer/delete automatically based on message type.\n"
            "  Common flags: replace-origin replace-session-connection ICE=force\n"
            "  Example: rtpengine_manage(\"replace-origin replace-session-connection\");"
        ),
        "is_method": (
            "is_method(\"METHOD\") — Check SIP method\n"
            "  Returns TRUE if the current message matches the given method.\n"
            "  Example: if (is_method(\"INVITE\")) { ... }\n"
            "  Can also check multiple: is_method(\"INVITE|UPDATE\")"
        ),
        "has_totag": (
            "has_totag() — Check if To header has a tag\n"
            "  Returns TRUE if To header contains a ;tag= parameter.\n"
            "  Commonly used to distinguish in-dialog requests:\n"
            "    if (has_totag()) { /* in-dialog */ } else { /* initial */ }"
        ),
        "record_route": (
            "record_route() — Add Record-Route header\n"
            "  Ensures subsequent in-dialog requests pass through this proxy.\n"
            "  Must be called before relaying initial INVITE.\n"
            "  Example: record_route(); t_relay();"
        ),
        "sl_send_reply": (
            "sl_send_reply(code, reason) — Stateless reply\n"
            "  Sends a SIP reply without creating a transaction.\n"
            "  Example: sl_send_reply(\"404\", \"Not Found\");"
        ),
        "t_relay": (
            "t_relay() — Stateful relay\n"
            "  Forwards the request statefully (creates transaction).\n"
            "  Handles retransmissions automatically.\n"
            "  Example: if (!t_relay()) { sl_reply_error(); }"
        ),
        "xlog": (
            "xlog(\"fmt\") — Log with variable substitution\n"
            "  Supports $var, $ru, $fu, etc. in format string.\n"
            "  Example: xlog(\"Calling $ru from $fu\\n\");\n"
            "  Levels: xlog(\"L_WARN\", \"message\")\n"
            "  Shortcut: xdbg(\"message\")  (equivalent to xlog(\"L_DBG\", ...))"
        ),
        "save": (
            "save(\"table\") — Save registration\n"
            "  Saves the current REGISTER to the specified location table.\n"
            "  Example: save(\"location\");\n"
            "  Returns: 1 on success, -1 on error"
        ),
        "lookup": (
            "lookup(\"table\") — Lookup registered contact\n"
            "  Sets $ru to the registered contact URI.\n"
            "  Example: if (!lookup(\"location\")) { sl_send_reply(\"404\", \"Not Found\"); }\n"
            "  Returns: 1 if found, -1 if not found"
        ),
        "subst": (
            "subst(\"/pattern/replacement/flags\") — Regex substitution on message\n"
            "  Modifies the SIP message body in-place.\n"
            "  Example: subst(\"/From:.*sip:([^@]+)@/From: <sip:\\1@new.host>/\");"
        ),
        "append_hf": (
            "append_hf(\"header: value\") — Append SIP header\n"
            "  Adds a new header at the end of the message headers.\n"
            "  Example: append_hf(\"X-Custom: value\\r\\n\");"
        ),
        "remove_hf": (
            "remove_hf(\"header\") — Remove SIP header\n"
            "  Removes all occurrences of the specified header.\n"
            "  Example: remove_hf(\"X-Custom\");"
        ),
    }

    name_lower = name.lower().strip("$").strip("()")
    for key in help_db:
        if key.lower().replace("()", "") == name_lower:
            return help_db[key]

    return None


def _get_all_completions() -> list[str]:
    return [
        "$var(", "$avp(", "$hdr(",
        "$ru", "$fu", "$tu", "$ci", "$cs", "$rm",
        "$si", "$sp", "$Ri", "$Rp",
        "$ft", "$tt", "$ct", "$ua", "$cl",
        "is_method(", "has_totag(", "ds_select_dst(", "ds_select_domain(",
        "rtpengine_manage(", "rtpengine_offer(", "rtpengine_answer(",
        "sl_send_reply(", "t_relay(", "t_newtran(", "t_reply(",
        "record_route(", "save(", "lookup(", "registered(",
        "append_hf(", "remove_hf(", "is_present_hf(",
        "subst(", "subst_hf(", "subst_uri(",
        "forward(", "relay(",
        "xlog(", "xdbg(",
        "send_reply(", "msg_apply_changes(",
        "setflag(", "resetflag(", "isflagset(",
        "drop", "exit", "return",
        "%%sip", "%%kamcmd", "%%vars", "%%flow", "%%reset", "%%help",
        "{uri.user}", "{uri.host}", "{uri.port}",
        "{s.len}", "{s.int}", "{s.upper}", "{s.lower}",
        "{s.trim}", "{s.escape}", "{s.unescape}",
        "{nameaddr.uri}", "{nameaddr.name}", "{nameaddr.params}",
    ]


def _get_general_help() -> str:
    return (
        "Kamailio CFG Notebook Kernel v0.3.0\n"
        "====================================\n\n"
        "Magics:\n"
        "  %%sip INVITE|REGISTER|BYE  — Create mock SIP message\n"
        "  %%kamcmd <command>         — Run kamcmd against live Kamailio\n"
        "  %%vars                     — Display all variables\n"
        "  %%flow                     — Show SIP flow diagram\n"
        "  %%trace                    — Trace route block execution (v0.2)\n"
        "  %%diff                     — Show variable state diff (v0.3)\n"
        "  %%kamailio status|start|stop — Control local Kamailio (v0.3)\n"
        "  %%reset                    — Clear all state\n"
        "  %%help [topic]             — Show help for a function/variable\n\n"
        "Examples:\n"
        '  $var(x) = 10;\n'
        '  $ru = "sip:1002@10.0.0.1";\n'
        '  xlog("Calling $(ru{uri.user})\\n");\n'
        '  if (is_method("INVITE")) { xlog("Got INVITE\\n"); }\n\n'
        "Type %%help <function> for specific help.\n"
        "e.g.: %%help ds_select_dst"
    )


if __name__ == "__main__":
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=KamailioKernel)
