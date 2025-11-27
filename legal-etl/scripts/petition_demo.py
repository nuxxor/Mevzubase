"""
Quick demo to generate a petition draft with the standalone module.

Usage:
    python -m scripts.petition_demo --mode static --format txt
    python -m scripts.petition_demo --mode qwen --format html
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petitions import LocalQwenClient, PetitionInput, PetitionService  # type: ignore
from petitions.llm import StaticLLMClient  # type: ignore
from petitions.schema import Evidence, Fact, Party  # type: ignore


def build_sample_input() -> PetitionInput:
    return PetitionInput(
        petition_type="dava_dilekcesi",
        court="ANKARA ASLİYE HUKUK MAHKEMESİ",
        subject="Alacak talebi",
        parties=[
            Party(role="davaci", name="Ahmet Yılmaz", tc_id="12345678901", address="Ankara"),
            Party(role="davali", name="Mehmet Demir", address="İstanbul"),
        ],
        facts=[
            Fact(summary="01.01.2023 tarihli sözleşme imzalandı.", evidence_refs=["Ek-1"]),
            Fact(summary="Sözleşme bedeli ödenmedi.", evidence_refs=["Ek-2"]),
        ],
        legal_basis=["TBK m. 117", "HMK m. 119"],
        requests=["Alacağın faiziyle tahsiline"],
        evidence=[
            Evidence(label="Ek-1", description="Sözleşme"),
            Evidence(label="Ek-2", description="Dekont"),
        ],
    )


def main(mode: str, output: Path, fmt: str) -> None:
    sample_input = build_sample_input()
    if mode == "static":
        mock = {
            "subject": "Alacak davası",
            "facts": [
                "01.01.2023 tarihli sözleşme imzalandı.",
                "Sözleşme bedeli ödenmedi.",
            ],
            "legal_basis": ["TBK m. 117", "HMK m. 119"],
            "evidence": ["Ek-1: Sözleşme", "Ek-2: Dekont"],
            "requests": ["Alacağın faiziyle tahsiline"],
            "missing_fields": [],
        }
        llm_client = StaticLLMClient(text=json.dumps(mock))
    else:
        llm_client = LocalQwenClient()

    service = PetitionService(llm_client)
    output_obj = service.build(sample_input)
    if fmt == "txt":
        content = output_obj.text
    else:
        content = output_obj.html or output_obj.text
    output.write_text(content, encoding="utf-8")
    print(f"--- Taslak ({fmt}) ---\n{content}\n")
    if output_obj.qa_warnings:
        print("Uyarılar:", output_obj.qa_warnings)
    else:
        print("Uyarı yok.")
    print(f"Kaydedildi: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["static", "qwen"], default="static")
    parser.add_argument("--output", type=Path, default=Path("petition_draft.txt"))
    parser.add_argument("--format", choices=["txt", "html"], default="txt")
    args = parser.parse_args()
    main(mode=args.mode, output=args.output, fmt=args.format)
