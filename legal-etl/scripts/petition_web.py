"""
Basit lokal web arayüzü (dependency-free) ile dilekçe demo.

Çalıştır:
    python -m scripts.petition_web --mode qwen --port 8000

Varsayılan form alanları minimumdur; test amaçlıdır.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petitions import LocalQwenClient, PetitionInput, PetitionService  # type: ignore
from petitions.llm import StaticLLMClient  # type: ignore
from petitions.schema import Evidence, Fact, Party  # type: ignore


def _render_form(output_html: str = "", warnings: list[str] | None = None) -> str:
    warn_html = ""
    if warnings:
        warn_html = "<div style='color:red;'><strong>Uyarılar:</strong><ul>" + "".join(
            f"<li>{html.escape(w)}</li>" for w in warnings
        ) + "</ul></div>"

    return f"""
    <html><head><meta charset="utf-8"><title>Dilekçe Demo</title></head>
    <body style="font-family:Arial, sans-serif; margin:20px;">
      <h2>Dilekçe Demo</h2>
      <form method="POST">
        <label>Mahkeme:</label><br/>
        <input type="text" name="court" value="ANKARA ASLİYE HUKUK MAHKEMESİ" size="60"/><br/><br/>
        <label>Dava Konusu:</label><br/>
        <input type="text" name="subject" value="Alacak talebi" size="60"/><br/><br/>
        <label>Davacı (isim|tc|adres):</label><br/>
        <input type="text" name="davaci" value="Ahmet Yılmaz|12345678901|Ankara" size="60"/><br/><br/>
        <label>Davalı (isim|tc|adres):</label><br/>
        <input type="text" name="davali" value="Mehmet Demir||İstanbul" size="60"/><br/><br/>
        <label>Olgular (satır bazlı):</label><br/>
        <textarea name="facts" rows="4" cols="80">01.01.2023 tarihli sözleşme imzalandı.
Sözleşme bedeli ödenmedi.</textarea><br/><br/>
        <label>Hukuki Sebepler (virgülle):</label><br/>
        <input type="text" name="legal_basis" value="TBK m. 117, HMK m. 119" size="60"/><br/><br/>
        <label>Talepler (satır bazlı):</label><br/>
        <textarea name="requests" rows="2" cols="80">Alacağın faiziyle tahsiline</textarea><br/><br/>
        <input type="submit" value="Taslak üret"/>
      </form>
      {warn_html}
      <h3>Taslak</h3>
      <div style="border:1px solid #ccc; padding:10px;">{output_html}</div>
    </body></html>
    """


def _build_input(form: dict[str, list[str]]) -> PetitionInput:
    def get(name: str, default: str = "") -> str:
        return form.get(name, [default])[0].strip()

    davaci_raw = get("davaci")
    davali_raw = get("davali")

    def parse_party(raw: str, role: str) -> Party:
        parts = raw.split("|")
        name = parts[0].strip() if parts else ""
        tc = parts[1].strip() if len(parts) > 1 else None
        addr = parts[2].strip() if len(parts) > 2 else None
        return Party(role=role, name=name, tc_id=tc or None, address=addr or None)

    facts = [line.strip() for line in get("facts").splitlines() if line.strip()]
    requests = [line.strip() for line in get("requests").splitlines() if line.strip()]
    legal_basis = [item.strip() for item in get("legal_basis").split(",") if item.strip()]

    parties = [parse_party(davaci_raw, "davaci")]
    if davali_raw:
        parties.append(parse_party(davali_raw, "davali"))

    return PetitionInput(
        petition_type="dava_dilekcesi",
        court=get("court"),
        subject=get("subject"),
        parties=parties,
        facts=[Fact(summary=f, evidence_refs=[]) for f in facts],
        legal_basis=legal_basis,
        requests=requests,
        evidence=[Evidence(label="Ek-1", description="Sözleşme"), Evidence(label="Ek-2", description="Dekont")],
    )


def make_handler(service: PetitionService):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _render_form()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length).decode("utf-8")
            form = parse_qs(data)
            try:
                petition_input = _build_input(form)
                output = service.build(petition_input)
                content = output.html or html.escape(output.text).replace("\n", "<br/>")
                body = _render_form(content, output.qa_warnings)
            except Exception as exc:  # pragma: no cover - interactive
                body = f"<pre>Hata: {html.escape(str(exc))}</pre>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode("utf-8"))

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["static", "qwen"], default="static")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.mode == "static":
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
    handler = make_handler(service)
    server = HTTPServer(("0.0.0.0", args.port), handler)
    print(f"Web arayüzü http://localhost:{args.port} üzerinde.")
    server.serve_forever()


if __name__ == "__main__":
    main()
