from ado_mcp.utils import branch_ref, build_steps, html_to_text, parse_steps, short_ref, wiql_str


def test_steps_roundtrip():
    steps = [{"action": "Open <login> page", "expected": "Form is shown"}, {"action": "Click"}]
    parsed = parse_steps(build_steps(steps))
    assert parsed == [
        {"step": 1, "action": "Open <login> page", "expected": "Form is shown"},
        {"step": 2, "action": "Click", "expected": ""},
    ]


def test_html_to_text():
    assert html_to_text("<div>a<br>b&nbsp;c</div>") == "a\nb c"
    assert html_to_text(None) == ""


def test_wiql_escape():
    assert wiql_str("o'k") == "o''k"


def test_refs():
    assert branch_ref("main") == "refs/heads/main"
    assert branch_ref("refs/heads/dev") == "refs/heads/dev"
    assert short_ref("refs/heads/feature/x") == "feature/x"
