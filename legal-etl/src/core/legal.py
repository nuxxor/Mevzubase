from __future__ import annotations

import re
from typing import Iterable

LAW_TAGS = {
    "6098": "TBK",
    "6100": "HMK",
    "5237": "TCK",
    "5271": "CMK",
    "6102": "TTK",
}

TOPIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("kira tespiti", ("kira", "tespit")),
    ("TBK 344", ("kira", "uyarlama")),
    ("mülkiyet hakkı", ("mülkiyet",)),
    ("ifade özgürlüğü", ("ifade özgürlüğü",)),
)


def normalize_case_number(value: str | None) -> str:
    if not value:
        return ""
    text = value.upper().replace(":", " ").replace("\t", " ")
    text = text.replace("ESAS", "E").replace("KARAR", "K").replace("NO", "")
    match = re.search(r"(\d{4})[^\d]*(\d+)", text)
    if not match:
        return text.strip().replace(" ", "")
    return f"{match.group(1)}/{match.group(2)}"


def _case_aliases(prefix: str, raw: str) -> set[str]:
    normalized = normalize_case_number(raw)
    if not normalized:
        return set()
    core = normalized
    label = {"E": "Esas", "K": "Karar", "B": "Basvuru"}.get(prefix.upper(), prefix.upper())
    return {
        f"{prefix.upper()}.{core}",
        f"{prefix.upper()} {core}",
        f"{label} {core}",
        core,
    }


def _article_aliases(article_no: str | None, law_no: str | None) -> set[str]:
    aliases: set[str] = set()
    if not article_no:
        return aliases
    article = article_no.replace("MADDE", "m.").replace(" ", "")
    aliases.update({article, article.replace("m.", "m"), article.replace("m.", "madde ")})
    if law_no:
        aliases.add(f"{law_no} {article}")
        aliases.add(f"{law_no}/{article.replace('m.', '')}")
    return aliases


def build_aliases(
    e_no: str | None,
    k_no: str | None,
    chamber: str | None,
    law_no: str | None = None,
    article_no: str | None = None,
    b_no: str | None = None,
) -> list[str]:
    aliases: set[str] = set()
    if e_no:
        aliases.update(_case_aliases("E", e_no))
    if k_no:
        aliases.update(_case_aliases("K", k_no))
    if b_no:
        aliases.update(_case_aliases("B", b_no))
    if chamber:
        aliases.update(
            {
                chamber,
                chamber.replace(" ", ""),
                chamber.upper(),
            }
        )
    if law_no:
        aliases.update({law_no, f"Kanun {law_no}"})
    aliases.update(_article_aliases(article_no, law_no))
    return sorted(alias for alias in aliases if alias)


def normalize_chamber(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    bam_match = re.match(
        r"(?P<city>[A-ZÇĞİÖŞÜa-zçğıöşü ]+?)\s+Bölge\s+Adliye\s+Mahkemesi\s+(?P<num>\d+)\.?\s*(?P<branch>Hukuk|Ceza)\s+Dairesi",
        text,
        re.IGNORECASE,
    )
    if bam_match:
        city = bam_match.group("city").strip()
        num = bam_match.group("num")
        branch = bam_match.group("branch")
        suffix = "HD" if branch.lower().startswith("h") else "CD"
        return f"{city} BAM {num}.{suffix}"

    match = re.match(r"(?P<num>\d+)\.?\s*(?P<branch>Hukuk|Ceza)\s+Dairesi", text, re.IGNORECASE)
    if match:
        num = match.group("num")
        branch = match.group("branch")
        suffix = "HD" if branch.lower().startswith("h") else "CD"
        return f"{num}.{suffix}"

    if "Genel Kurul" in text:
        return "GK"
    return text


def infer_topic_tags(text: str | None) -> list[str]:
    if not text:
        return []
    lowered = text.lower()
    tags: set[str] = set()
    for tag, keywords in TOPIC_RULES:
        if all(keyword in lowered for keyword in keywords):
            tags.add(tag)
    for code, law_tag in LAW_TAGS.items():
        if code in lowered or law_tag.lower() in lowered:
            tags.add(law_tag)
    return sorted(tags)


def has_keywords(text: str | None, keywords: Iterable[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return all(keyword.lower() in lowered for keyword in keywords)
