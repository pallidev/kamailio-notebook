"""Kamailio cfg expression parser and executor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .sip_message import SIPMessage
from .transforms import parse_transforms, evaluate_transform_chain, TRANSFORMS
from .variables import VarValue, VarType, VariableStore


@dataclass
class ExecutionResult:
    output: list[str] = field(default_factory=list)
    variables_changed: dict[str, tuple[str, str]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)
    branches: list[str] = field(default_factory=list)


class CfgExecutor:
    """Parses and executes Kamailio cfg code line by line."""

    def __init__(self, vars: VariableStore, message: Optional[SIPMessage] = None):
        self.vars = vars
        self.message = message

    def execute_cell(self, code: str) -> ExecutionResult:
        result = ExecutionResult()

        lines = code.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                i += 1
                continue

            # xlog / xdbg
            if self._exec_log(line, result):
                i += 1
                continue

            # Assignment: $var(x) = value; or $ru = "value";
            if self._exec_assignment(line, result):
                i += 1
                continue

            # if (...) { ... } else { ... }
            if line.startswith("if") and "(" in line:
                consumed = self._exec_if_block(lines, i, result)
                i += consumed
                continue

            # route(name) call
            route_match = re.match(r'route\((\w+)\)\s*;?', line)
            if route_match:
                result.output.append(f"→ route({route_match.group(1)}) called")
                result.trace.append(f"route({route_match.group(1)})")
                i += 1
                continue

            # Simple function calls: func_name(params);
            if self._exec_function(line, result):
                i += 1
                continue

            # drop / exit / return
            if line.rstrip(";").strip() in ("drop", "exit", "return",
                                              "drop()", "exit()", "return()"):
                result.output.append(f"→ {line.rstrip(';').strip()} executed")
                result.trace.append(line.rstrip(";").strip())
                i += 1
                continue

            # send_reply(code, "reason")
            sr_match = re.match(r'send_reply\((\d+)\s*,\s*"([^"]+)"\)\s*;?', line)
            if sr_match:
                code_val = sr_match.group(1)
                reason = sr_match.group(2)
                result.output.append(f"→ send_reply({code_val}, \"{reason}\")")
                result.trace.append(f"send_reply({code_val}, \"{reason}\")")
                i += 1
                continue

            result.errors.append(f"Unknown statement: {line}")
            i += 1

        return result

    def _exec_assignment(self, line: str, result: ExecutionResult) -> bool:
        """Handle variable assignment: $var(x) = value;"""
        match = re.match(
            r'(\$[\w.(){}]+)\s*=\s*(.+?)\s*;?\s*$',
            line
        )
        if not match:
            return False

        target = match.group(1)
        raw_value = match.group(2).rstrip(";").strip()

        value = self._evaluate_expression(raw_value)
        old = self.vars.get(target)
        self.vars.set(target, value)

        result.variables_changed[target] = (f"{old}", f"{value}")
        result.output.append(f"{target} = {value}  ({value.type.value})")
        result.trace.append(f"assign: {target} = {value}")
        return True

    def _exec_log(self, line: str, result: ExecutionResult) -> bool:
        """Handle xlog/xdbg."""
        match = re.match(r'(?:xlog|xdbg)\s*\(\s*"(.+?)"\s*\)\s*;?', line)
        if not match:
            return False

        fmt = match.group(1)
        output = self._format_string(fmt)
        result.output.append(f"[LOG] {output}")
        result.trace.append(f"xlog: {output}")
        return True

    def _exec_if_block(self, lines: list[str], start: int, result: ExecutionResult) -> int:
        """Execute an if/else block. Returns number of lines consumed."""
        # Collect all lines of the if block
        block_lines, consumed = self._collect_block(lines, start)
        if block_lines is None:
            return consumed

        # Parse condition — match balanced parentheses
        first = block_lines[0]
        condition = self._extract_if_condition(first)
        if condition is None:
            result.errors.append(f"Cannot parse if condition: {first}")
            return consumed
        cond_result = self._evaluate_condition(condition)

        # Split into if-body and else-body
        if_body, else_body = self._split_if_else(block_lines[1:])

        if cond_result:
            result.output.append(f"✓ if ({condition}) → TRUE")
            result.branches.append(f"if({condition}): TRUE")
            sub = self.execute_cell("\n".join(if_body))
            result.output.extend(sub.output)
            result.trace.extend(sub.trace)
            result.variables_changed.update(sub.variables_changed)
        else:
            if else_body:
                result.output.append(f"✗ if ({condition}) → FALSE → else")
                result.branches.append(f"if({condition}): FALSE → else")
                sub = self.execute_cell("\n".join(else_body))
                result.output.extend(sub.output)
                result.trace.extend(sub.trace)
                result.variables_changed.update(sub.variables_changed)
            else:
                result.output.append(f"✗ if ({condition}) → FALSE")
                result.branches.append(f"if({condition}): FALSE")

        return consumed

    def _collect_block(self, lines: list[str], start: int) -> tuple[Optional[list[str]], int]:
        """Collect a complete if/else block spanning multiple lines."""
        collected = []
        i = start
        brace_depth = 0
        found_brace = False

        while i < len(lines):
            line = lines[i].strip()
            collected.append(line)

            for ch in line:
                if ch == "{":
                    brace_depth += 1
                    found_brace = True
                elif ch == "}":
                    brace_depth -= 1

            if found_brace and brace_depth <= 0:
                return collected, len(collected)

            i += 1

            # Single-line if without braces: "if (...) statement;"
            if not found_brace and i < len(lines):
                next_line = lines[i].strip()
                if not next_line.startswith("else") and ";" in line and brace_depth == 0:
                    return collected, len(collected)

        return collected, len(collected)

    def _split_if_else(self, body_lines: list[str]) -> tuple[list[str], list[str]]:
        """Split body lines into if-body and else-body."""
        if_lines = []
        else_lines = []
        in_else = False
        brace_depth = 0

        for line in body_lines:
            stripped = line.strip()

            if stripped == "}" or stripped == "} else {":
                in_else = True
                continue

            if stripped.startswith("else"):
                in_else = True
                remaining = stripped[4:].strip()
                if remaining.startswith("{"):
                    remaining = remaining[1:].strip()
                if remaining:
                    else_lines.append(remaining)
                continue

            if stripped in ("{", "}"):
                continue

            if in_else:
                else_lines.append(line)
            else:
                if_lines.append(line)

        return if_lines, else_lines

    def _extract_if_condition(self, line: str) -> Optional[str]:
        """Extract condition from 'if (condition) {' handling nested parens."""
        match = re.match(r'if\s*\(', line)
        if not match:
            return None

        start = match.end()
        depth = 1
        i = start
        in_string = False
        string_char = None

        while i < len(line):
            ch = line[i]

            if in_string:
                if ch == string_char:
                    in_string = False
            elif ch in ('"', "'"):
                in_string = True
                string_char = ch
            elif ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return line[start:i].strip()

            i += 1

        return line[start:].rstrip("){").strip()

    def _exec_function(self, line: str, result: ExecutionResult) -> bool:
        """Handle common function calls."""
        known_functions = {
            "sl_send_reply", "sl_reply_error",
            "ds_select_dst", "ds_select_domain", "ds_next_dst", "ds_next_domain", "ds_mark_dst",
            "rtpengine_manage", "rtpengine_delete", "rtpengine_offer", "rtpengine_answer",
            "is_method", "has_totag", "isflagset", "setflag", "resetflag",
            "save", "lookup", "registered",
            "append_hf", "remove_hf", "is_present_hf",
            "msg_apply_changes",
            "subst", "subst_hf", "subst_uri",
            "forward", "relay",
            "t_newtran", "t_reply", "t_relay",
            "record_route",
        }

        match = re.match(r'(\w+)\s*\(([^)]*)\)\s*;?', line)
        if not match:
            return False

        func_name = match.group(1)
        func_args = match.group(2)

        if func_name not in known_functions:
            return False

        # Evaluate arguments
        args_resolved = self._resolve_function_args(func_args)
        result.output.append(f"→ {func_name}({args_resolved})")
        result.trace.append(f"{func_name}({args_resolved})")

        # Special handling for some functions
        if func_name == "is_method":
            method = args_resolved.strip('"').strip("'")
            current = self.vars.get("$rm").to_str() if self.vars.get("$rm").type != VarType.NULL else ""
            is_match = method.strip('"').upper() == current.upper()
            result.output.append(f"  result: {'TRUE' if is_match else 'FALSE'} (current method: {current})")
            return True

        if func_name == "has_totag":
            has = bool(self.vars.get("$tt").to_str()) if self.vars.get("$tt").type != VarType.NULL else False
            result.output.append(f"  result: {'TRUE' if has else 'FALSE'}")
            return True

        return True

    def _resolve_function_args(self, args_str: str) -> str:
        """Resolve variables in function arguments."""
        def replacer(m):
            var_name = m.group(0)
            val = self.vars.get(var_name)
            if val.type != VarType.NULL:
                return val.to_str()
            return var_name

        return re.sub(r'\$[\w.(){}]+', replacer, args_str)

    def _evaluate_expression(self, expr: str) -> VarValue:
        """Evaluate a cfg expression to a VarValue."""
        expr = expr.strip()

        # String literal
        if expr.startswith('"') and expr.endswith('"'):
            content = expr[1:-1]
            content = self._format_string(content)
            return VarValue(VarType.STRING, content)

        # Integer literal
        if re.match(r'^-?\d+$', expr):
            return VarValue(VarType.INTEGER, int(expr))

        # Null
        if expr in ("$null", "null"):
            return VarValue(VarType.NULL, None)

        # String concatenation: "hello" + " world"
        if "+" in expr:
            parts = re.split(r'\s*\+\s*', expr)
            values = [self._evaluate_expression(p) for p in parts]
            if all(v.type == VarType.INTEGER for v in values):
                total = sum(v.value for v in values)
                return VarValue(VarType.INTEGER, total)
            combined = "".join(v.to_str() for v in values)
            return VarValue(VarType.STRING, combined)

        # Variable with transforms: $(ru{uri.user})
        if "{" in expr:
            base, transforms = parse_transforms(expr)
            base_val = self.vars.get(base)
            if base_val.type == VarType.NULL:
                return VarValue(VarType.STRING, f"<undefined: {base}>")
            return evaluate_transform_chain(base_val, transforms)

        # Simple variable reference
        if expr.startswith("$"):
            val = self.vars.get(expr)
            if val.type != VarType.NULL:
                return val
            return VarValue(VarType.STRING, f"<undefined: {expr}>")

        # Fallback: treat as string
        return VarValue(VarType.STRING, expr)

    def _evaluate_condition(self, cond: str) -> bool:
        """Evaluate a simple if condition."""
        cond = cond.strip()

        # Method check: is_method("INVITE")
        method_match = re.match(r'is_method\s*\(\s*"(\w+)"\s*\)', cond)
        if method_match:
            expected = method_match.group(1).upper()
            current = self.vars.get("$rm").to_str().upper()
            return current == expected

        # has_totag()
        if cond.strip() in ("has_totag()", "has_totag"):
            has = bool(self.vars.get("$tt").to_str())
            return has

        # Negation: !expr
        if cond.startswith("!"):
            return not self._evaluate_condition(cond[1:].strip())

        # Comparison with ==
        eq_match = re.match(r'(.+?)\s*==\s*(.+)', cond)
        if eq_match:
            left = self._evaluate_expression(eq_match.group(1).strip())
            right = self._evaluate_expression(eq_match.group(2).strip())
            return left.to_str() == right.to_str()

        # Comparison with !=
        neq_match = re.match(r'(.+?)\s*!=\s*(.+)', cond)
        if neq_match:
            left = self._evaluate_expression(neq_match.group(1).strip())
            right = self._evaluate_expression(neq_match.group(2).strip())
            return left.to_str() != right.to_str()

        # Comparison with > or <
        gt_match = re.match(r'(.+?)\s*>\s*(.+)', cond)
        if gt_match:
            left = self._evaluate_expression(gt_match.group(1).strip())
            right = self._evaluate_expression(gt_match.group(2).strip())
            return left.to_int() > right.to_int()

        lt_match = re.match(r'(.+?)\s*<\s*(.+)', cond)
        if lt_match:
            left = self._evaluate_expression(lt_match.group(1).strip())
            right = self._evaluate_expression(lt_match.group(2).strip())
            return left.to_int() < right.to_int()

        # =~ regex match
        regex_match = re.match(r'(.+?)\s*=~\s*"(.+)"', cond)
        if regex_match:
            val = self._evaluate_expression(regex_match.group(1).strip()).to_str()
            pattern = regex_match.group(2)
            return bool(re.search(pattern, val))

        # Truthy check: variable or function result
        val = self._evaluate_expression(cond)
        if val.type == VarType.INTEGER:
            return val.value != 0
        if val.type == VarType.STRING:
            return len(val.value) > 0 and val.value != "0"

        return False

    def _format_string(self, fmt: str) -> str:
        """Format a string with variable substitution."""
        def replacer(match):
            var_expr = match.group(0)
            if "{" in var_expr:
                base, transforms = parse_transforms(var_expr)
                val = self.vars.get(base)
                if val.type == VarType.NULL:
                    return var_expr
                result = evaluate_transform_chain(val, transforms)
                return result.to_str()
            val = self.vars.get(var_expr)
            if val.type != VarType.NULL:
                return val.to_str()
            return var_expr

        # Match: $ru, $fu, $var(x), $(ru), $(ru{uri.user}), $(var(x){s.len})
        return re.sub(r'\$\([\w.]+(?:\{[^}]+\})*\)|\$[\w]+', replacer, fmt)
