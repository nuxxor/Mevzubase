from __future__ import annotations

from datetime import date
from typing import List, Set

from .schema import GeneratedSections, PetitionInput
from .templates import PetitionTemplate


def _roles(parties) -> Set[str]:
    return {p.role for p in parties}


def run_basic_qa(
    petition_input: PetitionInput,
    sections: GeneratedSections,
    template: PetitionTemplate,
    rendered_text: str | None = None,
) -> List[str]:
    warnings: List[str] = []
    roles = _roles(petition_input.parties)

    if not petition_input.subject.strip():
        warnings.append("Dava konusu boş.")

    upper_court = petition_input.court.upper()
    if "MAHKEMES" not in upper_court and "BAŞSAVCILIĞI" not in upper_court:
        warnings.append("Mahkeme/bulunduğu makam adı eksik veya hatalı görünüyor.")

    if "davaci" not in roles and "davaci_vekili" not in roles:
        warnings.append("Davacı/vekili belirtilmemiş.")

    if petition_input.petition_type not in {"suc_duyurusu"} and "davali" not in roles and "davali_vekili" not in roles:  # noqa: E501
        warnings.append("Davalı/vekili belirtilmemiş.")

    if petition_input.petition_type in {"istinaf", "temyiz"} and not petition_input.decision_reference:
        warnings.append("İstinaf/temyiz için karar numarası/tarihi eksik.")

    if not petition_input.service_date and petition_input.petition_type in {"istinaf", "temyiz"}:
        warnings.append("Tebliğ tarihi belirtilmemiş (süre kontrolü yapın).")

    if not sections.facts:
        warnings.append("Açıklamalar/fakt alanı boş.")

    if not sections.requests:
        warnings.append("Sonuç ve istem bölümü boş.")

    today = date.today()
    if petition_input.service_date and petition_input.service_date > today:
        warnings.append("Tebliğ tarihi gelecekte görünüyor, kontrol edin.")

    if petition_input.legal_basis and not sections.legal_basis:
        warnings.append("Hukuki sebepler girdide vardı ancak taslakta görünmüyor.")

    if petition_input.evidence and not sections.evidence:
        warnings.append("Deliller girdide vardı ancak taslakta görünmüyor.")

    evidence_labels = {ev.label for ev in petition_input.evidence}
    missing_refs = {
        ref for fact in petition_input.facts for ref in fact.evidence_refs if ref not in evidence_labels
    }
    if missing_refs:
        warnings.append(f"Delil referansı eşleşmedi: {', '.join(sorted(missing_refs))}")

    if rendered_text:
        lower = rendered_text.lower()
        first_person = [" ben ", " biz ", " bana ", " beni ", " bizim ", " bize ", "bizler"]
        if any(token in lower for token in first_person):
            warnings.append("Metinde birinci tekil/çoğul dil tespit edildi (resmi tondan kaçının).")

    return warnings
