"""Tests for the VarDiffTable and KamailioController."""

import pytest
from kamailio_notebook.kamailio_control import VarDiffTable, VarSnapshot


class TestVarDiffTable:
    def test_diff_added(self):
        before = VarSnapshot(variables={"$ru": "sip:1001@a"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "sip:1001@a", "$fu": "sip:1002@b"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        assert diff["$fu"] == ("", "sip:1002@b", "added")

    def test_diff_removed(self):
        before = VarSnapshot(variables={"$ru": "sip:1001@a", "$fu": "sip:1002@b"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "sip:1001@a"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        assert diff["$fu"] == ("sip:1002@b", "", "removed")

    def test_diff_changed(self):
        before = VarSnapshot(variables={"$ru": "sip:1001@a"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "sip:1002@b"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        assert diff["$ru"] == ("sip:1001@a", "sip:1002@b", "changed")

    def test_diff_unchanged(self):
        before = VarSnapshot(variables={"$ru": "same"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "same"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        assert diff["$ru"] == ("same", "same", "unchanged")

    def test_render_text_only_shows_changes(self):
        before = VarSnapshot(variables={"$ru": "old"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "new", "$fu": "added"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        text = VarDiffTable.render_text(diff)
        assert "$ru" in text
        assert "$fu" in text

    def test_render_html(self):
        before = VarSnapshot(variables={"$ru": "old"}, timestamp="before")
        after = VarSnapshot(variables={"$ru": "new"}, timestamp="after")
        diff = VarDiffTable.diff(before, after)
        html = VarDiffTable.render_html(diff)
        assert "<table" in html
        assert "$ru" in html
