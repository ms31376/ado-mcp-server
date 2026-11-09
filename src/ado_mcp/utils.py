"""Formatting helpers."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any


def wiql_str(value: str) -> str:
    """Escape a value for a WIQL string literal."""
    return value.replace("'", "''")


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", value, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    lines = [line.strip() for line in s.splitlines()]
    return "\n".join(line for line in lines if line)


def text_to_html(value: str) -> str:
    return html.escape(value).replace("\n", "<br>")


def person(value: Any) -> str | None:
    if isinstance(value, dict):
        return value.get("displayName") or value.get("uniqueName")
    return value


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        v = re.sub(r"\.(\d{6})\d+", r".\1", value.replace("Z", "+00:00"))
        return datetime.fromisoformat(v)
    except ValueError:
        return None


def branch_ref(branch: str | None) -> str | None:
    if not branch:
        return None
    return branch if branch.startswith("refs/") else f"refs/heads/{branch}"


def short_ref(ref: str | None) -> str | None:
    if ref and ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return ref


def parse_steps(xml_str: str | None) -> list[dict]:
    """Parse Microsoft.VSTS.TCM.Steps XML into [{step, action, expected}]."""
    if not xml_str:
        return []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return [{"raw": html_to_text(xml_str)}]
    steps: list[dict] = []
    for el in root:
        if el.tag == "step":
            ps = el.findall("parameterizedString")
            steps.append({
                "step": len(steps) + 1,
                "action": html_to_text(ps[0].text) if ps else "",
                "expected": html_to_text(ps[1].text) if len(ps) > 1 else "",
            })
        elif el.tag == "compref":
            steps.append({"step": len(steps) + 1, "shared_steps_id": int(el.get("ref", 0))})
    return steps


def build_steps(steps: list[dict]) -> str:
    """Build Microsoft.VSTS.TCM.Steps XML from [{action, expected}]."""
    parts = [f'<steps id="0" last="{len(steps) + 1}">']
    for i, s in enumerate(steps, start=2):
        action_text = str(s.get("action", ""))
        expected_text = str(s.get("expected", ""))
        action = html.escape(f"<DIV><P>{html.escape(action_text)}</P></DIV>")
        expected = html.escape(f"<DIV><P>{html.escape(expected_text)}</P></DIV>") if expected_text else ""
        kind = "ValidateStep" if expected_text else "ActionStep"
        parts.append(
            f'<step id="{i}" type="{kind}">'
            f'<parameterizedString isformatted="true">{action}</parameterizedString>'
            f'<parameterizedString isformatted="true">{expected}</parameterizedString>'
            f'<description/></step>')
    parts.append("</steps>")
    return "".join(parts)


def tail(lines: list[str], n: int) -> list[str]:
    return lines[-n:] if n and len(lines) > n else lines
