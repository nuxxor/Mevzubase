from __future__ import annotations

import re
from typing import Iterable

BASE_NOISE_PATTERNS: tuple[str, ...] = (
    r"DataTable",
    r"recordsTotal",
    r"recordsFiltered",
    r"lengthMenu",
    r"pixel-ratio",
    r"toastr",
    r"datepicker",
    r"selectpicker",
    r"autoclose",
    r"liveSearch",
    r"actionsBox",
    r"toast-top-right",
    r"fullScreen",
    r"apexcharts",
    r"countTo",
    r"Yardım",
    r"Kapat",
    r"No'ya Göre",
    r"Büyüğe Göre",
    r"Küçüğe Göre",
    r"İstatistik",
)


def strip_noise_lines(text: str | None, extra_patterns: Iterable[str] | None = None) -> str:
    """Strip UI/script noise while bırak meaningful hukuk satırları."""

    if not text:
        return ""

    patterns = list(BASE_NOISE_PATTERNS)
    if extra_patterns:
        patterns.extend(extra_patterns)

    filtered: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(re.search(pat, line, re.IGNORECASE) for pat in patterns):
            continue
        filtered.append(line)
    return "\n".join(filtered)
