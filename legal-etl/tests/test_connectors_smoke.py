from datetime import date
from pathlib import Path

from src.connectors.spk import SPKConnector
from src.connectors.yargitay import YargitayConnector
from src.connectors.emsal import EmsalConnector

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "sample_html"


def test_yargitay_smoke():
    connector = YargitayConnector(fixture_dir=FIXTURES)
    refs = list(connector.list_items(date.today()))
    assert refs, "list_items should yield at least one ref"
    raw = connector.fetch(refs[0])
    assert raw.content_html
    doc = connector.parse(raw)
    assert doc.doc_id.startswith("yargitay:")
    chunks = connector.chunk(doc)
    assert chunks


def test_spk_smoke():
    connector = SPKConnector(fixture_dir=FIXTURES)
    refs = list(connector.list_items(date.today()))
    assert refs
    raw = connector.fetch(refs[0])
    assert raw.content_html
    doc = connector.parse(raw)
    assert doc.doc_id.startswith("spk:")
    chunks = connector.chunk(doc)
    assert len(chunks) >= 2


def test_emsal_smoke():
    connector = EmsalConnector(fixture_dir=FIXTURES)
    refs = list(connector.list_items(date.today()))
    assert refs
    raw = connector.fetch(refs[0])
    assert raw.content_html
    doc = connector.parse(raw)
    assert doc.doc_id.startswith("emsal:")
    chunks = connector.chunk(doc)
    assert chunks
