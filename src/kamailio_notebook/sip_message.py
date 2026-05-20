"""SIP message mock for simulating incoming messages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# SIP method constants
INVITE = "INVITE"
REGISTER = "REGISTER"
BYE = "BYE"
ACK = "ACK"
CANCEL = "CANCEL"
OPTIONS = "OPTIONS"
SUBSCRIBE = "SUBSCRIBE"
NOTIFY = "NOTIFY"
MESSAGE = "MESSAGE"
INFO = "INFO"
PRACK = "PRACK"
UPDATE = "UPDATE"
REFER = "REFER"
PUBLISH = "PUBLISH"

VALID_METHODS = {
    INVITE, REGISTER, BYE, ACK, CANCEL, OPTIONS,
    SUBSCRIBE, NOTIFY, MESSAGE, INFO, PRACK, UPDATE, REFER, PUBLISH,
}

# SIP response code categories
PROVISIONAL = range(100, 200)
SUCCESS = range(200, 300)
REDIRECT = range(300, 400)
CLIENT_ERROR = range(400, 500)
SERVER_ERROR = range(500, 600)
GLOBAL_ERROR = range(600, 700)


@dataclass
class SIPHeader:
    name: str
    value: str


@dataclass
class SIPMessage:
    """Mock SIP message that mimics what Kamailio receives."""

    method: str
    request_uri: str
    from_uri: str
    from_tag: str = ""
    from_display: str = ""
    to_uri: str = ""
    to_tag: str = ""
    to_display: str = ""
    call_id: str = ""
    cseq: str = "1"
    cseq_method: str = ""
    via: list[str] = field(default_factory=list)
    contact: str = ""
    content_type: str = ""
    content_length: str = "0"
    body: str = ""
    headers: list[SIPHeader] = field(default_factory=list)

    # Kamailio pseudo-variable equivalents
    src_ip: str = "127.0.0.1"
    src_port: int = 5060
    dst_ip: str = "127.0.0.1"
    dst_port: int = 5060
    proto: str = "UDP"

    @classmethod
    def from_raw(cls, method: str, raw_text: str) -> SIPMessage:
        """Parse a mock SIP message from text (simplified)."""
        msg = cls(method=method, request_uri="", from_uri="")

        lines = raw_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse header: value
            if ":" in line:
                name, _, value = line.partition(":")
                name = name.strip().lower()
                value = value.strip()

                if name == "from":
                    msg.from_uri, msg.from_tag, msg.from_display = _parse_nameaddr(value)
                elif name == "to":
                    msg.to_uri, msg.to_tag, msg.to_display = _parse_nameaddr(value)
                elif name == "request-uri" or name == "r-uri":
                    msg.request_uri = value
                elif name == "contact":
                    msg.contact = value
                elif name == "call-id":
                    msg.call_id = value
                elif name == "cseq":
                    parts = value.split()
                    msg.cseq = parts[0] if parts else "1"
                    msg.cseq_method = parts[1] if len(parts) > 1 else method
                elif name == "via":
                    msg.via.append(value)
                elif name == "content-type":
                    msg.content_type = value
                elif name == "content-length":
                    msg.content_length = value
                else:
                    msg.headers.append(SIPHeader(name=name, value=value))

        if not msg.request_uri and msg.to_uri:
            msg.request_uri = msg.to_uri

        if not msg.cseq_method:
            msg.cseq_method = method

        if not msg.call_id:
            import uuid
            msg.call_id = str(uuid.uuid4())[:8] + "@mock"

        if not msg.from_tag:
            import uuid
            msg.from_tag = str(uuid.uuid4())[:8]

        return msg

    @property
    def fu(self) -> str:
        return self.from_uri

    @property
    def tu(self) -> str:
        return self.to_uri

    @property
    def ru(self) -> str:
        return self.request_uri

    @ru.setter
    def ru(self, value: str):
        self.request_uri = value

    def get_header(self, name: str) -> Optional[str]:
        name_lower = name.lower()
        for h in self.headers:
            if h.name.lower() == name_lower:
                return h.value
        return None

    def set_header(self, name: str, value: str):
        name_lower = name.lower()
        for h in self.headers:
            if h.name.lower() == name_lower:
                h.value = value
                return
        self.headers.append(SIPHeader(name=name, value=value))

    def format_display(self) -> str:
        lines = []
        lines.append(f"{self.method} {self.request_uri} SIP/2.0")
        if self.from_display:
            lines.append(f"From: \"{self.from_display}\" <{self.from_uri}>;tag={self.from_tag}")
        else:
            lines.append(f"From: <{self.from_uri}>;tag={self.from_tag}")
        if self.to_display:
            to_part = f"\"{self.to_display}\" <{self.to_uri}>"
        else:
            to_part = f"<{self.to_uri}>"
        if self.to_tag:
            to_part += f";tag={self.to_tag}"
        lines.append(f"To: {to_part}")
        lines.append(f"Call-ID: {self.call_id}")
        lines.append(f"CSeq: {self.cseq} {self.cseq_method}")
        for via in self.via:
            lines.append(f"Via: {via}")
        if self.contact:
            lines.append(f"Contact: {self.contact}")
        for h in self.headers:
            lines.append(f"{h.name}: {h.value}")
        return "\n".join(lines)


def _parse_nameaddr(value: str) -> tuple[str, str, str]:
    """Parse a SIP name-addr like '"Display" <sip:user@host>;tag=abc'."""
    display = ""
    tag = ""
    uri = value

    # Extract tag
    tag_match = re.search(r';tag=([^\s;>]+)', value)
    if tag_match:
        tag = tag_match.group(1)

    # Extract display name
    display_match = re.match(r'"([^"]+)"\s*<([^>]+)>', value)
    if display_match:
        display = display_match.group(1)
        uri = display_match.group(2)
    else:
        # Try <uri> format
        uri_match = re.search(r'<([^>]+)>', value)
        if uri_match:
            uri = uri_match.group(1)
        else:
            # Clean up tag from uri
            uri = re.sub(r';tag=[^\s;>]+', '', value).strip()

    return uri, tag, display
