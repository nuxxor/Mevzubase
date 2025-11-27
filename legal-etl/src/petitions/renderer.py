from __future__ import annotations

from datetime import date
import html
from typing import List

from .schema import GeneratedSections, Party, PetitionInput
from .templates import PetitionTemplate


def _render_parties(parties: List[Party]) -> List[str]:
    lines: List[str] = []
    for party in parties:
        label = party.role.upper().replace("_", " ")
        info = [party.name]
        if party.tc_id:
            info.append(f"TC: {party.tc_id}")
        if party.address:
            info.append(f"Adres: {party.address}")
        if party.representation:
            info.append(party.representation)
        lines.append(f"{label}: " + " | ".join(info))
    return lines


def _numbered(title: str, items: List[str]) -> List[str]:
    if not items:
        return []
    lines = [title]
    for idx, item in enumerate(items, start=1):
        lines.append(f"{idx}. {item}")
    return lines


def render_petition_text(
    petition_input: PetitionInput, template: PetitionTemplate, sections: GeneratedSections
) -> str:
    out: List[str] = []
    out.append(template.heading.format(court=petition_input.court))
    out.append("")

    if "parties" in template.sections_order:
        out.extend(_numbered("TARAFLAR:", _render_parties(petition_input.parties)))
        out.append("")

    if "decision_reference" in template.sections_order and petition_input.decision_reference:
        out.append(f"BAŞVURUSU YAPILAN KARAR: {petition_input.decision_reference}")
        out.append("")

    if "subject" in template.sections_order:
        out.append(f"DAVA KONUSU: {sections.subject or petition_input.subject}")
        out.append("")

    if "facts" in template.sections_order:
        out.extend(_numbered("AÇIKLAMALAR:", sections.facts))
        out.append("")

    if "legal_basis" in template.sections_order:
        basis = petition_input.legal_basis or sections.legal_basis
        out.append("HUKUKİ SEBEPLER: " + (", ".join(basis) if basis else "Belirtilmedi"))
        out.append("")

    if "evidence" in template.sections_order:
        ev_list = sections.evidence or [ev.label for ev in petition_input.evidence]
        out.extend(_numbered("DELİLLER:", ev_list))
        out.append("")

    if "requests" in template.sections_order:
        out.extend(_numbered("SONUÇ ve İSTEM:", sections.requests))
        out.append("")

    if "date_signature" in template.sections_order:
        out.append(f"Tarih: {date.today().isoformat()}")
        out.append("İmza")
        out.append("")

    if "attachments" in template.sections_order and petition_input.evidence:
        out.append("EKLER:")
        for idx, ev in enumerate(petition_input.evidence, start=1):
            label = ev.label or f"Ek-{idx}"
            desc = f"{label} - {ev.description}" if ev.description else label
            out.append(f"Ek-{idx}: {desc}")

    if template.closing:
        out.append("")
        out.append(template.closing)

    return "\n".join(out)


def _esc(text: str) -> str:
    return html.escape(text)


def render_petition_html(
    petition_input: PetitionInput, template: PetitionTemplate, sections: GeneratedSections
) -> str:
    parts: List[str] = []
    parts.append(
        "<style>body{font-family:'Times New Roman',serif;font-size:14px;line-height:1.5;} h1{text-align:center;font-size:18px;} h2{margin-top:12px;} ul,ol{padding-left:20px;} .section{margin-bottom:12px;}</style>"  # noqa: E501
    )
    parts.append(f"<h1>{_esc(template.heading.format(court=petition_input.court))}</h1>")

    def section(title: str, content: str) -> None:
        parts.append(f'<div class="section"><h2>{_esc(title)}</h2>{content}</div>')

    if "parties" in template.sections_order:
        items = "".join(f"<li>{_esc(line)}</li>" for line in _render_parties(petition_input.parties))
        section("Taraflar", f"<ul>{items}</ul>")

    if "decision_reference" in template.sections_order and petition_input.decision_reference:
        section("Başvurusu Yapılan Karar", f"<p>{_esc(petition_input.decision_reference)}</p>")

    if "subject" in template.sections_order:
        subject = sections.subject or petition_input.subject
        section("Dava Konusu", f"<p>{_esc(subject)}</p>")

    if "facts" in template.sections_order:
        facts = "".join(f"<li>{_esc(item)}</li>" for item in sections.facts)
        section("Açıklamalar", f"<ol>{facts}</ol>")

    if "legal_basis" in template.sections_order:
        basis = petition_input.legal_basis or sections.legal_basis
        content = ", ".join(_esc(b) for b in basis) if basis else "Belirtilmedi"
        section("Hukuki Sebepler", f"<p>{content}</p>")

    if "evidence" in template.sections_order:
        ev_list = sections.evidence or [ev.label for ev in petition_input.evidence]
        ev_html = "".join(f"<li>{_esc(item)}</li>" for item in ev_list)
        section("Deliller", f"<ol>{ev_html}</ol>")

    if "requests" in template.sections_order:
        req_html = "".join(f"<li>{_esc(item)}</li>" for item in sections.requests)
        section("Sonuç ve İstem", f"<ol>{req_html}</ol>")

    if "date_signature" in template.sections_order:
        section("Tarih ve İmza", f"<p>{date.today().isoformat()}</p><p>İmza</p>")

    if "attachments" in template.sections_order and petition_input.evidence:
        items = []
        for idx, ev in enumerate(petition_input.evidence, start=1):
            label = ev.label or f"Ek-{idx}"
            desc = f"{label} - {ev.description}" if ev.description else label
            items.append(f"<li>Ek-{idx}: {_esc(desc)}</li>")
        section("Ekler", f"<ul>{''.join(items)}</ul>")

    if template.closing:
        parts.append(f"<p>{_esc(template.closing)}</p>")

    return "\n".join(parts)
