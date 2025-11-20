from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Sequence

from playwright.sync_api import APIResponse, Browser, BrowserContext, Page, Playwright, sync_playwright


@dataclass
class DocRequestTemplate:
    method: str
    url_template: str
    body_template: str | None
    headers: dict[str, str]


class PlaywrightSession:
    """Shared Playwright oturumu: tek browser/context, kaynak engelleme, request kısayolu."""

    def __init__(
        self,
        headless: bool = True,
        executable_path: str | None = None,
        block_resources: Iterable[str] | None = None,
        user_agents: Sequence[str] | None = None,
    ) -> None:
        self.headless = headless
        self.executable_path = executable_path
        self.block_resources = set(block_resources or {"image", "media", "font"})
        self.user_agents = user_agents or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        )
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._doc_template: DocRequestTemplate | None = None
        self._list_template: DocRequestTemplate | None = None

    def new_page(self) -> Page:
        context = self._ensure_context()
        page = context.new_page()
        page.set_default_timeout(10000)
        return page

    def remember_doc_request(self, response, doc_id: str | None) -> None:
        """Capture request template (URL/body) to tekrar kullan."""
        if not doc_id or self._doc_template:
            return
        try:
            request = response.request
            url_template = request.url.replace(doc_id, "{doc_id}")
            body_template = request.post_data
            if body_template:
                body_template = body_template.replace(doc_id, "{doc_id}")
            headers = {
                key: value
                for key, value in request.headers.items()
                if key.lower() in {"x-requested-with", "content-type", "referer", "accept"}
            }
            if "x-requested-with" not in {k.lower() for k in headers}:
                headers["X-Requested-With"] = "XMLHttpRequest"
            self._doc_template = DocRequestTemplate(
                method=request.method,
                url_template=url_template,
                body_template=body_template,
                headers=headers,
            )
        except Exception:
            return

    def remember_list_request(self, response) -> None:
        """Capture Detaylı Arama listesi request template; doc_id keşfi için kullanılacak."""
        if self._list_template:
            return
        try:
            request = response.request
            self._list_template = DocRequestTemplate(
                method=request.method,
                url_template=request.url,
                body_template=request.post_data,
                headers={
                    key: value
                    for key, value in request.headers.items()
                    if key.lower() in {"x-requested-with", "content-type", "referer", "accept"}
                },
            )
        except Exception:
            return

    def fetch_document(self, doc_id: str | None) -> APIResponse | None:
        if not doc_id:
            return None
        context = self._ensure_context()
        if not self._doc_template:
            return self._fetch_direct_document(context, doc_id)
        template = self._doc_template
        url = template.url_template.replace("{doc_id}", doc_id)
        data = template.body_template.replace("{doc_id}", doc_id) if template.body_template else None
        try:
            response = context.request.fetch(
                url,
                method=template.method,
                headers=template.headers,
                data=data,
                timeout=20000,
            )
        except Exception:
            return None
        if not response.ok:
            return None
        return response

    def fetch_list_rows(
        self,
        chamber: str | None,
        e_no: str | None,
        k_no: str | None,
        decision_date: str | None,
    ) -> list[dict]:
        """Detaylı arama listesini aynı şablonla (POST) tetikler; JSON satırlarını döner."""
        template = self._list_template
        if not template:
            return []
        context = self._ensure_context()
        data = self._build_list_payload(
            template.body_template,
            chamber=chamber,
            e_no=e_no,
            k_no=k_no,
            decision_date=decision_date,
        )
        try:
            response = context.request.fetch(
                template.url_template,
                method=template.method,
                headers=template.headers,
                data=data,
                timeout=30000,
            )
        except Exception:
            return []
        if not response.ok:
            return []
        try:
            ct = (response.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                payload = response.json()
            else:
                payload = response.text()
            return self._extract_json_rows(payload)
        except Exception:
            return []
        return []

    def _fetch_direct_document(self, context: BrowserContext, doc_id: str) -> APIResponse | None:
        try:
            response = context.request.get(
                f"https://karararama.yargitay.gov.tr/getDokuman?id={doc_id}",
                headers={
                    "x-requested-with": "XMLHttpRequest",
                    "referer": "https://karararama.yargitay.gov.tr/",
                    "accept": "application/json,text/html,*/*",
                },
                timeout=20000,
            )
        except Exception:
            return None
        if not response.ok:
            return None
        return response

    def close(self) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._context = None
        self._pw = None
        self._doc_template = None
        self._list_template = None

    def reset_context(self, restart_browser: bool = False) -> None:
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        self._context = None
        self._doc_template = None

        if restart_browser:
            try:
                if self._browser:
                    self._browser.close()
            except Exception:
                pass
            self._browser = None
            try:
                if self._pw:
                    self._pw.stop()
            except Exception:
                pass
            self._pw = None

    def _ensure_context(self) -> BrowserContext:
        if self._context:
            try:
                # Accessing .pages will raise if context kapandı
                _ = self._context.pages
                return self._context
            except Exception:
                try:
                    self._context.close()
                except Exception:
                    pass
                self._context = None
        if not self._pw:
            self._pw = sync_playwright().start()
        if not self._browser:
            self._browser = self._pw.chromium.launch(
                headless=self.headless,
                executable_path=self.executable_path,
                args=["--no-sandbox", "--disable-setuid-sandbox"],
            )
        self._context = self._browser.new_context(
            locale="tr-TR",
            user_agent=random.choice(list(self.user_agents)),
            viewport={"width": 1280, "height": 900},
        )
        if self.block_resources:
            try:
                self._context.route("**/*", self._route_blocker)
            except Exception:
                pass
        return self._context

    def _route_blocker(self, route) -> None:
        if route.request.resource_type in self.block_resources:
            return route.abort()
        return route.continue_()

    def _extract_json_rows(self, data) -> list[dict]:
        rows: list[dict] = []
        try:
            if isinstance(data, list):
                for el in data:
                    if isinstance(el, dict):
                        rows.append(el)
            elif isinstance(data, dict):
                for key in ("data", "results", "rows"):
                    if isinstance(data.get(key), list):
                        rows.extend([el for el in data[key] if isinstance(el, dict)])
                inner = data.get("data")
                if isinstance(inner, dict):
                    for key in ("data", "rows", "results"):
                        if isinstance(inner.get(key), list):
                            rows.extend([el for el in inner[key] if isinstance(el, dict)])
        except Exception:
            pass
        return rows

    def _build_list_payload(
        self,
        body_template: str | None,
        chamber: str | None,
        e_no: str | None,
        k_no: str | None,
        decision_date: str | None,
    ) -> str | None:
        if not body_template:
            return None
        from urllib.parse import urlencode, parse_qsl
        import json

        e_year, e_seq = self._split_case_number(e_no)
        k_year, k_seq = self._split_case_number(k_no)

        def _apply_overrides(pairs: dict) -> dict:
            for key in list(pairs.keys()):
                lkey = key.lower()
                if decision_date and any(tok in lkey for tok in ("bas", "start", "from")) and ("tarih" in lkey or "date" in lkey):
                    pairs[key] = decision_date
                if decision_date and any(tok in lkey for tok in ("bit", "end", "son", "to")) and ("tarih" in lkey or "date" in lkey):
                    pairs[key] = decision_date
                if chamber and "daire" in lkey:
                    pairs[key] = chamber
                if e_year and "esas" in lkey and "y" in lkey:
                    pairs[key] = e_year
                if e_seq and "esas" in lkey and "no" in lkey:
                    pairs[key] = e_seq
                if k_year and "karar" in lkey and "y" in lkey:
                    pairs[key] = k_year
                if k_seq and "karar" in lkey and "no" in lkey:
                    pairs[key] = k_seq
            return pairs

        body = body_template.strip()
        if body.startswith("{"):
            try:
                payload = json.loads(body)
            except Exception:
                return body_template
            if isinstance(payload, dict):
                payload = _apply_overrides(payload)
                try:
                    return json.dumps(payload)
                except Exception:
                    return body_template
            return body_template

        try:
            pairs = parse_qsl(body, keep_blank_values=True)
        except Exception:
            return body_template
        mapped = {}
        for k, v in pairs:
            if k not in mapped:
                mapped[k] = v
        mapped = _apply_overrides(mapped)
        try:
            return urlencode(mapped)
        except Exception:
            return body_template

    def _split_case_number(self, number_str: str | None) -> tuple[str | None, str | None]:
        if not number_str:
            return None, None
        import re

        year_match = re.search(r"(\d{4})", number_str)
        seq_match = re.search(r"/(\d+)", number_str)
        return (year_match.group(1) if year_match else None, seq_match.group(1) if seq_match else None)

    @property
    def list_url(self) -> str | None:
        if self._list_template:
            return self._list_template.url_template
        return None
