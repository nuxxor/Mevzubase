from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .schema import PetitionType


@dataclass(frozen=True)
class PetitionTemplate:
    petition_type: PetitionType
    heading: str
    sections_order: List[str]
    closing: str = "Saygılarımızla arz ederiz."


TEMPLATES: Dict[PetitionType, PetitionTemplate] = {
    "dava_dilekcesi": PetitionTemplate(
        petition_type="dava_dilekcesi",
        heading="{court}\n\nSAYIN MAHKEMESİ'NE",
        sections_order=[
            "parties",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
    "cevap_dilekcesi": PetitionTemplate(
        petition_type="cevap_dilekcesi",
        heading="{court}\n\nSAYIN MAHKEMESİ'NE",
        sections_order=[
            "parties",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
    "istinaf": PetitionTemplate(
        petition_type="istinaf",
        heading="{court}\n\nBÖLGE ADLİYE MAHKEMESİ'NE",
        sections_order=[
            "parties",
            "decision_reference",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
    "temyiz": PetitionTemplate(
        petition_type="temyiz",
        heading="{court}\n\nT.C. YARGITAY BAŞKANLIĞI'NA",
        sections_order=[
            "parties",
            "decision_reference",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
    "idari": PetitionTemplate(
        petition_type="idari",
        heading="{court}\n\nSAYIN İDARİ MAHKEMESİ'NE",
        sections_order=[
            "parties",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
    "suc_duyurusu": PetitionTemplate(
        petition_type="suc_duyurusu",
        heading="{court}\n\nCUMHURİYET BAŞSAVCILIĞI'NA",
        sections_order=[
            "parties",
            "subject",
            "facts",
            "legal_basis",
            "evidence",
            "requests",
            "date_signature",
            "attachments",
        ],
    ),
}
