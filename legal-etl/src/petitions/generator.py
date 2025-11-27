from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

import orjson

from .llm import LLMClient
from .qa import run_basic_qa
from .renderer import render_petition_html, render_petition_text
from .schema import GeneratedSections, PetitionInput, PetitionOutput
from .templates import PetitionTemplate, TEMPLATES


SYSTEM_PROMPT = """Sen, Türk hukuku dilekçe üreticisisin.
Türkçe, resmi ve üçüncü tekil çoğul tonunu koru. Yeni olgu uydurma; yalnızca verilen verileri kullan.
Her iddiayı kanıtlarla eşleştir, boş alanları belirtme.
Kısaltmaları olduğu gibi koru (HMK, TBK vb.); asla açma, değiştirme veya yeniden adlandırma.
Hukuki sebepler alanını girdideki listeyle birebir aynı tut (sırayı koru, yeni ekleme/çıkarma yapma).
Faktları sadece yeniden ifade et; taraf/kişi/bedel ekleme, yeni detay üretme.
ÇIKTIYI SADECE JSON olarak döndür. Biçim:
{
  "subject": "...",
  "facts": ["...", "..."],
  "legal_basis": ["..."],
  "evidence": ["Ek-1: ...", "..."],
  "requests": ["..."],
  "tone_notes": "opsiyonel",
  "missing_fields": ["..."]
}
Başka açıklama ekleme.
"""


def _build_user_prompt(petition_input: PetitionInput) -> str:
    as_dict = petition_input.model_dump()
    return "Girdi verileri (JSON):\n" + json.dumps(as_dict, ensure_ascii=False, indent=2)


def _parse_sections(raw_text: str, fallback: PetitionInput) -> GeneratedSections:
    try:
        data = orjson.loads(raw_text)
    except Exception:
        return GeneratedSections(
            subject=fallback.subject,
            facts=[f.summary for f in fallback.facts],
            legal_basis=fallback.legal_basis or [],
            evidence=[ev.label for ev in fallback.evidence],
            requests=fallback.requests,
            tone_notes="LLM JSON parse edilemedi, kullanıcı girdisiyle oluşturuldu.",
            missing_fields=[],
        )

    return GeneratedSections(
        subject=data.get("subject") or fallback.subject,
        facts=data.get("facts") or [f.summary for f in fallback.facts],
        legal_basis=data.get("legal_basis") or fallback.legal_basis,
        evidence=data.get("evidence") or [ev.label for ev in fallback.evidence],
        requests=data.get("requests") or fallback.requests,
        tone_notes=data.get("tone_notes"),
        missing_fields=data.get("missing_fields") or [],
    )


@dataclass
class PetitionGenerator:
    llm_client: LLMClient

    def generate_sections(self, petition_input: PetitionInput) -> GeneratedSections:
        prompt = f"{SYSTEM_PROMPT}\n\n{_build_user_prompt(petition_input)}"
        raw = self.llm_client.generate(prompt, temperature=0.15)
        return _parse_sections(raw, petition_input)

    def generate(
        self,
        petition_input: PetitionInput,
        template: PetitionTemplate | None = None,
    ) -> PetitionOutput:
        tpl = template or TEMPLATES[petition_input.petition_type]
        sections = self.generate_sections(petition_input)
        text = render_petition_text(petition_input, tpl, sections)
        html = render_petition_html(petition_input, tpl, sections)
        warnings = run_basic_qa(petition_input, sections, tpl, rendered_text=text)
        return PetitionOutput(text=text, html=html, qa_warnings=warnings, sections=sections)


@dataclass
class PetitionService:
    llm_client: LLMClient

    def build(self, petition_input: PetitionInput, template: PetitionTemplate | None = None) -> PetitionOutput:
        generator = PetitionGenerator(self.llm_client)
        return generator.generate(petition_input, template=template)
