"""Tests for the Kamailio CFG executor."""

import pytest
from kamailio_notebook.cfg_executor import CfgExecutor
from kamailio_notebook.sip_message import SIPMessage
from kamailio_notebook.variables import VariableStore, VarType, VarValue
from kamailio_notebook.transforms import apply_transform, evaluate_transform_chain, parse_transforms


class TestVariableAssignment:
    def setup_method(self):
        self.vars = VariableStore()
        self.executor = CfgExecutor(self.vars)

    def test_string_assignment(self):
        result = self.executor.execute_cell('$var(name) = "hello";')
        assert any("hello" in line for line in result.output)
        assert self.vars.get("$var(name)").value == "hello"

    def test_integer_assignment(self):
        result = self.executor.execute_cell("$var(count) = 42;")
        assert any("42" in line for line in result.output)
        assert self.vars.get("$var(count)").value == 42

    def test_variable_concatenation(self):
        self.executor.execute_cell('$var(first) = "hello";')
        self.executor.execute_cell('$var(second) = " world";')
        result = self.executor.execute_cell('$var(greeting) = $var(first) + $var(second);')
        val = self.vars.get("$var(greeting)")
        assert val.value == "hello world"

    def test_integer_arithmetic(self):
        self.executor.execute_cell("$var(a) = 10;")
        self.executor.execute_cell("$var(b) = 20;")
        result = self.executor.execute_cell("$var(c) = $var(a) + $var(b);")
        assert self.vars.get("$var(c)").value == 30

    def test_message_variable_set(self):
        result = self.executor.execute_cell('$ru = "sip:1002@10.0.0.1";')
        assert self.vars.get("$ru").value == "sip:1002@10.0.0.1"


class TestSIPMessage:
    def test_parse_invite(self):
        msg = SIPMessage.from_raw("INVITE", """
From: <sip:1001@example.com>;tag=abc123
To: <sip:1002@example.com>
Contact: <sip:1001@192.168.1.1:5060>
""")
        assert msg.method == "INVITE"
        assert msg.from_uri == "sip:1001@example.com"
        assert msg.from_tag == "abc123"
        assert msg.to_uri == "sip:1002@example.com"
        assert msg.request_uri == "sip:1002@example.com"
        assert msg.contact == "<sip:1001@192.168.1.1:5060>"

    def test_parse_display_name(self):
        msg = SIPMessage.from_raw("INVITE", """
From: "Alice" <sip:alice@example.com>;tag=xyz
To: "Bob" <sip:bob@example.com>
""")
        assert msg.from_display == "Alice"
        assert msg.from_uri == "sip:alice@example.com"
        assert msg.to_display == "Bob"

    def test_init_variables(self):
        msg = SIPMessage.from_raw("REGISTER", """
From: <sip:1001@example.com>;tag=reg1
To: <sip:1001@example.com>
""")
        vars = VariableStore()
        vars.init_from_message(msg)
        assert vars.get("$rm").value == "REGISTER"
        assert vars.get("$fu").value == "sip:1001@example.com"


class TestTransformations:
    def test_uri_user(self):
        val = VarValue(VarType.STRING, "sip:1002@10.0.0.1:5060")
        result = apply_transform(val, "uri.user")
        assert result.value == "1002"

    def test_uri_host(self):
        val = VarValue(VarType.STRING, "sip:1002@10.0.0.1:5060")
        result = apply_transform(val, "uri.host")
        assert result.value == "10.0.0.1"

    def test_uri_port(self):
        val = VarValue(VarType.STRING, "sip:1002@10.0.0.1:5060")
        result = apply_transform(val, "uri.port")
        assert result.value == 5060

    def test_s_len(self):
        val = VarValue(VarType.STRING, "hello")
        result = apply_transform(val, "s.len")
        assert result.value == 5

    def test_s_upper(self):
        val = VarValue(VarType.STRING, "hello")
        result = apply_transform(val, "s.upper")
        assert result.value == "HELLO"

    def test_s_lower(self):
        val = VarValue(VarType.STRING, "HELLO")
        result = apply_transform(val, "s.lower")
        assert result.value == "hello"

    def test_s_int(self):
        val = VarValue(VarType.STRING, "42")
        result = apply_transform(val, "s.int")
        assert result.value == 42

    def test_parse_transforms(self):
        base, transforms = parse_transforms("$(ru{uri.user})")
        assert base == "$ru"
        assert transforms == ["uri.user"]

    def test_transform_chain(self):
        val = VarValue(VarType.STRING, "sip:1002@10.0.0.1:5060")
        result = evaluate_transform_chain(val, ["uri.user", "s.upper"])
        assert result.value == "1002"


class TestIfElse:
    def setup_method(self):
        self.vars = VariableStore()
        self.vars.set("$rm", VarValue(VarType.STRING, "INVITE"))
        self.executor = CfgExecutor(self.vars)

    def test_if_true(self):
        result = self.executor.execute_cell('if (is_method("INVITE")) { xlog("is INVITE"); }')
        assert any("TRUE" in line for line in result.output)

    def test_if_false(self):
        result = self.executor.execute_cell('if (is_method("REGISTER")) { xlog("reg"); }')
        assert any("FALSE" in line for line in result.output)

    def test_equality_check(self):
        self.vars.set("$var(x)", VarValue(VarType.INTEGER, 10))
        result = self.executor.execute_cell('if ($var(x) == 10) { xlog("ten"); }')
        assert any("TRUE" in line for line in result.output)

    def test_negation(self):
        result = self.executor.execute_cell('if (!is_method("REGISTER")) { xlog("not reg"); }')
        assert any("TRUE" in line for line in result.output)


class TestXlog:
    def setup_method(self):
        self.vars = VariableStore()
        self.vars.set("$ru", VarValue(VarType.STRING, "sip:1002@10.0.0.1"))
        self.executor = CfgExecutor(self.vars)

    def test_simple_log(self):
        result = self.executor.execute_cell('xlog("hello world");')
        assert any("hello world" in line for line in result.output)

    def test_variable_in_log(self):
        result = self.executor.execute_cell('xlog("Calling $ru");')
        assert any("sip:1002@10.0.0.1" in line for line in result.output)


class TestFunctionExecution:
    def setup_method(self):
        self.vars = VariableStore()
        self.vars.set("$rm", VarValue(VarType.STRING, "INVITE"))
        self.executor = CfgExecutor(self.vars)

    def test_is_method(self):
        result = self.executor.execute_cell('is_method("INVITE");')
        assert any("TRUE" in line for line in result.output)

    def test_record_route(self):
        result = self.executor.execute_cell("record_route();")
        assert any("record_route" in line for line in result.output)

    def test_ds_select_dst(self):
        result = self.executor.execute_cell('ds_select_dst("1", "4");')
        assert any("ds_select_dst" in line for line in result.output)

    def test_send_reply(self):
        result = self.executor.execute_cell('send_reply(404, "Not Found");')
        assert any("404" in line for line in result.output)
        assert any("Not Found" in line for line in result.output)
