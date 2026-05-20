"""Kamailio transformation functions."""

from __future__ import annotations

import re

from .variables import VarValue, VarType


def _parse_sip_uri(uri: str) -> dict:
    """Parse a SIP URI like sip:user@host:port;params into components."""
    result = {"user": "", "host": "", "port": 0, "params": ""}

    # Strip < > if present
    uri = uri.strip()
    if uri.startswith("<") and uri.endswith(">"):
        uri = uri[1:-1]

    # Remove scheme
    if ":" in uri:
        _, _, uri = uri.partition(":")

    # Split params (after first ;)
    if ";" in uri:
        uri, _, result["params"] = uri.partition(";")

    # Split user@host:port
    if "@" in uri:
        user_part, _, host_part = uri.partition("@")
        result["user"] = user_part
    else:
        host_part = uri

    # Split host:port
    if ":" in host_part:
        host, _, port = host_part.partition(":")
        result["host"] = host
        try:
            result["port"] = int(port)
        except ValueError:
            pass
    else:
        result["host"] = host_part

    return result


# Registry of all supported transformations
TRANSFORMS: dict[str, callable] = {}


def register(name: str):
    """Decorator to register a transformation function."""
    def decorator(func):
        TRANSFORMS[name] = func
        return func
    return decorator


def apply_transform(value: VarValue, transform_name: str) -> VarValue:
    """Apply a named transformation to a variable value."""
    func = TRANSFORMS.get(transform_name)
    if func is None:
        return VarValue(VarType.STRING, f"<unknown transform: {transform_name}>")
    return func(value)


def parse_transforms(expr: str) -> tuple[str, list[str]]:
    """Parse 'value{tr1}{tr2}' into (value, [tr1, tr2])."""
    transforms = []
    remaining = expr

    while True:
        match = re.search(r'\{([^}]+)\}', remaining)
        if not match:
            break
        transforms.append(match.group(1))
        remaining = remaining[:match.start()] + remaining[match.end():]

    # Normalize: $(ru) → $ru, $var(x) stays as $var(x)
    base = remaining.strip()
    if re.match(r'^\$\(\w+\)$', base):
        inner = base[2:-1]
        if "(" not in inner:  # not $var(...)
            base = "$" + inner

    return base, transforms


def evaluate_transform_chain(value: VarValue, transforms: list[str]) -> VarValue:
    """Apply a chain of transformations to a value."""
    result = value
    for tr in transforms:
        result = apply_transform(result, tr)
    return result


# --- URI Transformations ---

@register("uri.user")
def uri_user(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, _parse_sip_uri(value.to_str())["user"])


@register("uri.host")
def uri_host(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, _parse_sip_uri(value.to_str())["host"])


@register("uri.port")
def uri_port(value: VarValue) -> VarValue:
    return VarValue(VarType.INTEGER, _parse_sip_uri(value.to_str())["port"])


@register("uri.params")
def uri_params(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, _parse_sip_uri(value.to_str())["params"])


# --- String Transformations ---

@register("s.len")
def s_len(value: VarValue) -> VarValue:
    return VarValue(VarType.INTEGER, len(value.to_str()))


@register("s.int")
def s_int(value: VarValue) -> VarValue:
    try:
        return VarValue(VarType.INTEGER, int(value.to_str()))
    except (ValueError, TypeError):
        return VarValue(VarType.INTEGER, 0)


@register("s.substr")
def s_substr(value: VarValue, _params: str = "") -> VarValue:
    return VarValue(VarType.STRING, value.to_str())


@register("s.upper")
def s_upper(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, value.to_str().upper())


@register("s.lower")
def s_lower(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, value.to_str().lower())


@register("s.trim")
def s_trim(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, value.to_str().strip())


@register("s.escape")
def s_escape(value: VarValue) -> VarValue:
    import html
    return VarValue(VarType.STRING, html.escape(value.to_str()))


@register("s.unescape")
def s_unescape(value: VarValue) -> VarValue:
    import html
    return VarValue(VarType.STRING, html.unescape(value.to_str()))


@register("s.encode.hexa")
def s_encode_hexa(value: VarValue) -> VarValue:
    return VarValue(VarType.STRING, value.to_str().encode().hex())


@register("s.decode.hexa")
def s_decode_hexa(value: VarValue) -> VarValue:
    try:
        return VarValue(VarType.STRING, bytes.fromhex(value.to_str()).decode())
    except (ValueError, TypeError):
        return VarValue(VarType.STRING, "")


@register("s.encode.base64")
def s_encode_base64(value: VarValue) -> VarValue:
    import base64
    return VarValue(VarType.STRING, base64.b64encode(value.to_str().encode()).decode())


@register("s.decode.base64")
def s_decode_base64(value: VarValue) -> VarValue:
    import base64
    try:
        return VarValue(VarType.STRING, base64.b64decode(value.to_str()).decode())
    except Exception:
        return VarValue(VarType.STRING, "")


# --- IP Transformations ---

@register("ip.isip")
def ip_isip(value: VarValue) -> VarValue:
    import ipaddress
    s = value.to_str()
    try:
        ipaddress.ip_address(s)
        return VarValue(VarType.INTEGER, 1)
    except ValueError:
        return VarValue(VarType.INTEGER, 0)


@register("ip.pton")
def ip_pton(value: VarValue) -> VarValue:
    import ipaddress
    try:
        addr = ipaddress.ip_address(value.to_str())
        return VarValue(VarType.STRING, addr.packed.hex())
    except ValueError:
        return VarValue(VarType.STRING, "")


# --- Param Transformations ---

@register("param.value")
def param_value(value: VarValue, param_name: str = "") -> VarValue:
    s = value.to_str()
    if not param_name:
        return VarValue(VarType.STRING, "")
    for part in s.split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            if k.strip() == param_name:
                return VarValue(VarType.STRING, v.strip())
    return VarValue(VarType.STRING, "")


@register("param.exist")
def param_exist(value: VarValue, param_name: str = "") -> VarValue:
    s = value.to_str()
    if not param_name:
        return VarValue(VarType.INTEGER, 0)
    for part in s.split(";"):
        k = part.split("=")[0].strip()
        if k == param_name:
            return VarValue(VarType.INTEGER, 1)
    return VarValue(VarType.INTEGER, 0)


# --- Nameaddr Transformations ---

@register("nameaddr.uri")
def nameaddr_uri(value: VarValue) -> VarValue:
    s = value.to_str()
    match = re.search(r'<([^>]+)>', s)
    if match:
        return VarValue(VarType.STRING, match.group(1))
    return VarValue(VarType.STRING, s)


@register("nameaddr.name")
def nameaddr_name(value: VarValue) -> VarValue:
    s = value.to_str()
    match = re.match(r'"([^"]+)"', s)
    if match:
        return VarValue(VarType.STRING, match.group(1))
    return VarValue(VarType.STRING, "")


@register("nameaddr.params")
def nameaddr_params(value: VarValue) -> VarValue:
    s = value.to_str()
    match = re.search(r'>;?(.*)', s)
    if match:
        return VarValue(VarType.STRING, match.group(1).strip())
    return VarValue(VarType.STRING, "")


# --- Re (Regex) Transformations ---

@register("re.subst")
def re_subst(value: VarValue, pattern: str = "") -> VarValue:
    if not pattern:
        return value
    try:
        result, _ = re.subn(pattern, "", value.to_str(), count=1)
        return VarValue(VarType.STRING, result)
    except re.error:
        return value
