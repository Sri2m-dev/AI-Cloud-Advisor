from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class RoiAssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inputs: set[str] = set()
        self.label_targets: set[str] = set()
        self.headings: list[str] = []
        self._heading = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "input" and attributes.get("id"):
            self.inputs.add(str(attributes["id"]))
        if tag == "label" and attributes.get("for"):
            self.label_targets.add(str(attributes["for"]))
        if tag in {"h1", "h2"}:
            self._heading = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h1", "h2"}:
            self._heading = False

    def handle_data(self, data: str) -> None:
        if self._heading and data.strip():
            self.headings.append(data.strip())


def test_roi_calculator_is_executable_transparent_and_labeled() -> None:
    content = (ROOT / "tools/sales/nexora_roi_calculator.html").read_text(encoding="utf-8")
    parser = RoiAssetParser()
    parser.feed(content)

    assert parser.inputs == parser.label_targets
    assert {"spend", "opportunity", "realization", "investment"}.issubset(parser.inputs)
    assert "Nexora ROI Calculator" in parser.headings
    assert "Results are not certified savings" in content
    assert "qualified*value('realization')/100" in content
    assert "net/investment*100" in content


def test_demo_script_and_faq_preserve_executive_truthfulness() -> None:
    script = (ROOT / "docs/sales/NEXORA_V2_DEMO_SCRIPT.md").read_text(encoding="utf-8")
    faq = (ROOT / "docs/sales/NEXORA_V2_BUYER_FAQ.md").read_text(encoding="utf-8")

    for decision_id in ("NXR-INV-204", "NXR-PORT-118", "NXR-RISK-071"):
        assert decision_id in script
    assert "UNKNOWN" in script
    assert "identified, evidence-qualified, approved, executed" in faq
    assert "guarantee savings" in faq


def test_launch_dashboard_is_evidence_driven_and_does_not_authorize_ga() -> None:
    dashboard = (
        ROOT / "docs/launch/NEXORA_V2_LAUNCH_READINESS_DASHBOARD.md"
    ).read_text(encoding="utf-8")
    launch_pack = (ROOT / "docs/launch/NEXORA_V2_LAUNCH_PACK.md").read_text(
        encoding="utf-8"
    )

    for gate in (
        "Executive browser review",
        "Independent CIO acceptance",
        "Root license",
        "Backup and restore rehearsal",
        "v2.0 release notes",
    ):
        assert gate in dashboard
    assert "NOT AUTHORIZED" in dashboard
    assert "No merge, tag, production deployment, customer outreach" in dashboard
    assert "Required additions before GA" in launch_pack
    assert "SYNTHETIC_DEMONSTRATION_DATA" in launch_pack
