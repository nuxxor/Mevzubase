import pytest

from petitions import PetitionInput, PetitionService
from petitions.llm import StaticLLMClient
from petitions.export import export_docx
from petitions.schema import Evidence, Fact, Party


def test_petition_pipeline_renders_text():
    mock_response = """
    {
      "subject": "Alacak davası",
      "facts": ["Taraflar arasında 01.01.2023 tarihli sözleşme imzalandı.", "Ödeme yapılmadı."],
      "legal_basis": ["TBK m. 117", "HMK m. 119"],
      "evidence": ["Ek-1: Sözleşme", "Ek-2: Dekont"],
      "requests": ["Alacağın faiziyle tahsili"],
      "missing_fields": []
    }
    """
    llm = StaticLLMClient(text=mock_response)
    service = PetitionService(llm)
    petition_input = PetitionInput(
        petition_type="dava_dilekcesi",
        court="ANKARA ASLİYE HUKUK MAHKEMESİ",
        subject="Alacak talebi",
        parties=[
            Party(role="davaci", name="Ahmet Yılmaz", tc_id="12345678901", address="Ankara"),
            Party(role="davali", name="Mehmet Demir", address="İstanbul"),
        ],
        facts=[
            Fact(summary="01.01.2023 sözleşmesi imzalandı.", evidence_refs=["Ek-1"]),
            Fact(summary="Bedel ödenmedi.", evidence_refs=["Ek-2"]),
        ],
        legal_basis=["TBK m. 117"],
        requests=["Alacağın tahsili"],
        evidence=[
            Evidence(label="Ek-1", description="Sözleşme"),
            Evidence(label="Ek-2", description="Dekont"),
        ],
    )

    output = service.build(petition_input)

    assert "ANKARA ASLİYE HUKUK MAHKEMESİ" in output.text
    assert "AÇIKLAMALAR" in output.text
    assert "SONUÇ ve İSTEM" in output.text
    assert "Ek-1: Sözleşme" in output.text
    assert output.html is not None and "<h1>" in output.html
    assert not output.qa_warnings
    assert output.sections.subject == "Alacak davası"


def test_qa_warnings_on_missing_fields():
    llm = StaticLLMClient(
        text="""{"subject": "", "facts": [], "legal_basis": [], "evidence": [], "requests": [], "missing_fields": ["facts"]}"""  # noqa: E501
    )
    service = PetitionService(llm)
    petition_input = PetitionInput(
        petition_type="dava_dilekcesi",
        court="ANKARA ASLİYE HUKUK MAHKEMESİ",
        subject="",
        parties=[Party(role="davaci", name="Ahmet")],
        facts=[Fact(summary="Olgu", evidence_refs=["Ek-1"])],
        requests=["Talep"],
        evidence=[],
    )
    output = service.build(petition_input)
    assert any("Dava konusu boş" in w for w in output.qa_warnings)
    assert any("Delil referansı eşleşmedi" in w for w in output.qa_warnings)


def test_docx_export(tmp_path):
    pytest.importorskip("docx")
    mock_response = """
    {
      "subject": "Test",
      "facts": ["Olgu"],
      "legal_basis": [],
      "evidence": [],
      "requests": ["Talep"],
      "missing_fields": []
    }
    """
    llm = StaticLLMClient(text=mock_response)
    service = PetitionService(llm)
    petition_input = PetitionInput(
        petition_type="dava_dilekcesi",
        court="ANKARA ASLİYE HUKUK MAHKEMESİ",
        subject="Test",
        parties=[Party(role="davaci", name="Ahmet")],
        facts=[Fact(summary="Olgu", evidence_refs=[])],
        requests=["Talep"],
    )
    output = service.build(petition_input)
    out_path = tmp_path / "draft.docx"
    export_docx(out_path, output)
    assert out_path.exists() and out_path.stat().st_size > 0


def test_tone_and_court_warning():
    mock_response = """
    {
      "subject": "Test",
      "facts": ["Ben çok mağdurum"],
      "legal_basis": [],
      "evidence": [],
      "requests": ["Biz istiyoruz"],
      "missing_fields": []
    }
    """
    llm = StaticLLMClient(text=mock_response)
    service = PetitionService(llm)
    petition_input = PetitionInput(
        petition_type="dava_dilekcesi",
        court="ABC",
        subject="Test",
        parties=[Party(role="davaci", name="Ahmet")],
        facts=[Fact(summary="Olgu", evidence_refs=[])],
        requests=["Talep"],
    )
    output = service.build(petition_input)
    assert any("Mahkeme/bulunduğu makam adı" in w for w in output.qa_warnings)
    assert any("birinci tekil" in w for w in output.qa_warnings)
