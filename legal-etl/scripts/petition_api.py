"""
Basit JSON API + minimal HTML form.

Çalıştır:
    python -m scripts.petition_api --mode qwen --port 9000

Endpoint:
- GET /          : Basit HTML form (CDN'siz, aynı origin)
- POST /generate : JSON ile dilekçe üretimi
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from petitions import LocalQwenClient, PetitionInput, PetitionService  # type: ignore
from petitions.llm import StaticLLMClient  # type: ignore
from petitions.schema import Evidence, Fact, Party  # type: ignore

HTML_PAGE = """<!doctype html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <title>Dilekçe Demo</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 16px; background: #f6f8fb; }
    h2 { margin-top: 0; }
    label { font-weight: 600; display:block; margin: 8px 0 4px; }
    textarea, input, select { width: 100%; box-sizing: border-box; margin: 2px 0 8px 0; padding: 6px; }
    .row { display: flex; gap: 16px; }
    .pane { flex: 1; background:#fff; padding:12px; border:1px solid #e2e6ef; border-radius:8px; box-shadow:0 1px 2px rgba(0,0,0,0.05); }
    .warn { background:#fff5f5; border:1px solid #f0c2c2; color:#a00; padding:8px; border-radius:6px; }
    .preview { border:1px solid #ddd; padding:10px; min-height:200px; background:#fff; border-radius:6px; }
    .badge { display:inline-block; padding:2px 6px; border-radius:4px; background:#eef2ff; color:#333; margin-right:4px; font-size:12px; }
    .list-item { border:1px solid #e6eaf2; padding:8px; border-radius:6px; margin-bottom:6px; background:#fafbff; }
    button { padding:8px 12px; margin-top:6px; }
    .btn-primary { background:#2563eb; color:#fff; border:none; border-radius:6px; }
    .btn-ghost { background:transparent; border:1px dashed #94a3b8; color:#475569; border-radius:6px; }
  </style>
</head>
<body>
  <h2>Dilekçe Editörü (Demo)</h2>
  <div class="row">
    <div class="pane">
      <label>Dilekçe Türü</label>
      <select id="petition_type">
        <option value="dava_dilekcesi" selected>Dava Dilekçesi</option>
        <option value="cevap_dilekcesi">Cevap Dilekçesi</option>
        <option value="istinaf">İstinaf</option>
        <option value="temyiz">Temyiz</option>
        <option value="idari">İdari</option>
        <option value="suc_duyurusu">Suç Duyurusu</option>
      </select>
      <label>Mahkeme</label>
      <input id="court" value="ANKARA ASLİYE HUKUK MAHKEMESİ"/>
      <label>Dava Konusu</label>
      <input id="subject" value="Alacak talebi"/>

      <div style="margin-top:12px;">
        <div class="badge">Taraflar</div>
        <div id="parties"></div>
        <button class="btn-ghost" type="button" onclick="addParty('davaci')">+ Davacı ekle</button>
        <button class="btn-ghost" type="button" onclick="addParty('davali')">+ Davalı ekle</button>
      </div>

      <div style="margin-top:12px;">
        <div class="badge">Olgular</div>
        <div id="facts_list"></div>
        <button class="btn-ghost" type="button" onclick="addFact()">+ Olgu ekle</button>
      </div>

      <label style="margin-top:12px;">Hukuki Sebepler (virgülle)</label>
      <input id="legal_basis" value="TBK m. 117, HMK m. 119"/>

      <div style="margin-top:12px;">
        <div class="badge">Talepler</div>
        <div id="requests_list"></div>
        <button class="btn-ghost" type="button" onclick="addRequest()">+ Talep ekle</button>
      </div>

      <div style="margin-top:12px;">
        <div class="badge">Deliller</div>
        <div id="evidence_list"></div>
        <button class="btn-ghost" type="button" onclick="addEvidence()">+ Delil ekle</button>
      </div>

      <button class="btn-primary" onclick="submitForm()">Taslak Üret</button>
      <div id="error" class="warn" style="display:none; margin-top:8px;"></div>
    </div>
    <div class="pane">
      <h3>Uyarılar</h3>
      <div id="warnings" class="warn" style="display:none;"></div>
      <h3>Taslak Önizleme</h3>
      <div id="preview" class="preview"><em>Henüz taslak yok</em></div>
    </div>
  </div>
<script>
let partyId = 0, factId = 0, reqId = 0, evId = 0;

function el(tag, attrs={}, children=[]) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k,v]) => node.setAttribute(k,v));
  (Array.isArray(children) ? children : [children]).forEach(c => {
    if (typeof c === 'string') node.appendChild(document.createTextNode(c));
    else node.appendChild(c);
  });
  return node;
}

function renderLists() {
  // parties
  const partiesDiv = document.getElementById('parties');
  if (!partiesDiv.dataset.init) {
    partiesDiv.dataset.init = "1";
    addParty('davaci', "Ahmet Yılmaz", "12345678901", "Ankara");
    addParty('davali', "Mehmet Demir", "11111111111", "İstanbul");
  }
}

function addParty(role="davaci", name="", tc="", addr="") {
  const container = document.getElementById('parties');
  const id = ++partyId;
  const div = el('div', {class:'list-item', 'data-id': id});
  div.appendChild(el('div', {}, [
    el('select', {id:`party_role_${id}`}, [
      el('option', {value:'davaci', selected: role==='davaci' ? 'selected' : null}, "Davacı"),
      el('option', {value:'davali', selected: role==='davali' ? 'selected' : null}, "Davalı"),
      el('option', {value:'davaci_vekili', selected: role==='davaci_vekili' ? 'selected' : null}, "Davacı Vekili"),
      el('option', {value:'davali_vekili', selected: role==='davali_vekili' ? 'selected' : null}, "Davalı Vekili"),
    ])
  ]));
  div.appendChild(el('input', {id:`party_name_${id}`, placeholder:'İsim', value:name}));
  div.appendChild(el('input', {id:`party_tc_${id}`, placeholder:'TC', value:tc}));
  div.appendChild(el('input', {id:`party_addr_${id}`, placeholder:'Adres', value:addr}));
  const btn = el('button', {type:'button', class:'btn-ghost'}, "Sil");
  btn.onclick = () => div.remove();
  div.appendChild(btn);
  container.appendChild(div);
}

function addFact(text="") {
  const container = document.getElementById('facts_list');
  const id = ++factId;
  const div = el('div', {class:'list-item', 'data-id': id});
  div.appendChild(el('textarea', {rows:'2', id:`fact_text_${id}`}, text));
  const evInput = el('input', {id:`fact_refs_${id}`, placeholder:'Delil referansları (virgülle, örn: Ek-1,Ek-2)'});
  div.appendChild(evInput);
  const btn = el('button', {type:'button', class:'btn-ghost'}, "Sil");
  btn.onclick = () => div.remove();
  div.appendChild(btn);
  container.appendChild(div);
}

function addRequest(text="") {
  const container = document.getElementById('requests_list');
  const id = ++reqId;
  const div = el('div', {class:'list-item', 'data-id': id});
  div.appendChild(el('textarea', {rows:'1', id:`req_text_${id}`}, text));
  const btn = el('button', {type:'button', class:'btn-ghost'}, "Sil");
  btn.onclick = () => div.remove();
  div.appendChild(btn);
  container.appendChild(div);
}

function addEvidence(label="", desc="") {
  const container = document.getElementById('evidence_list');
  const id = ++evId;
  const div = el('div', {class:'list-item', 'data-id': id});
  div.appendChild(el('input', {id:`ev_label_${id}`, placeholder:'Ek-1', value:label || `Ek-${id}`}));
  div.appendChild(el('input', {id:`ev_desc_${id}`, placeholder:'Açıklama', value:desc}));
  const btn = el('button', {type:'button', class:'btn-ghost'}, "Sil");
  btn.onclick = () => div.remove();
  div.appendChild(btn);
  container.appendChild(div);
}

function collectParties() {
  const arr = [];
  document.querySelectorAll('#parties .list-item').forEach(div => {
    const id = div.dataset.id;
    arr.push({
      role: document.getElementById(`party_role_${id}`).value,
      name: document.getElementById(`party_name_${id}`).value,
      tc_id: document.getElementById(`party_tc_${id}`).value,
      address: document.getElementById(`party_addr_${id}`).value,
    });
  });
  return arr;
}

function collectFacts() {
  const arr = [];
  document.querySelectorAll('#facts_list .list-item').forEach(div => {
    const id = div.dataset.id;
    const refs = document.getElementById(`fact_refs_${id}`).value
      .split(',').map(s => s.trim()).filter(Boolean);
    const text = document.getElementById(`fact_text_${id}`).value.trim();
    if (text) arr.push({ summary: text, evidence_refs: refs });
  });
  return arr;
}

function collectRequests() {
  const arr = [];
  document.querySelectorAll('#requests_list .list-item').forEach(div => {
    const id = div.dataset.id;
    const text = document.getElementById(`req_text_${id}`).value.trim();
    if (text) arr.push(text);
  });
  return arr;
}

function collectEvidence() {
  const arr = [];
  document.querySelectorAll('#evidence_list .list-item').forEach(div => {
    const id = div.dataset.id;
    const label = document.getElementById(`ev_label_${id}`).value.trim();
    const desc = document.getElementById(`ev_desc_${id}`).value.trim();
    if (label) arr.push({ label, description: desc || undefined });
  });
  return arr;
}

async function submitForm() {
  const payload = {
    petition_type: document.getElementById('petition_type').value,
    court: document.getElementById('court').value,
    subject: document.getElementById('subject').value,
    parties: collectParties(),
    facts: collectFacts(),
    legal_basis: document.getElementById('legal_basis').value.split(',').map(s => s.trim()).filter(Boolean),
    requests: collectRequests(),
    evidence: collectEvidence(),
  };
  const errBox = document.getElementById('error');
  const warnBox = document.getElementById('warnings');
  const preview = document.getElementById('preview');
  errBox.style.display = 'none';
  warnBox.style.display = 'none';
  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(await res.text());
    }
    const data = await res.json();
    preview.innerHTML = data.html || data.text || '';
    if (data.qa_warnings && data.qa_warnings.length) {
      warnBox.style.display = 'block';
      warnBox.innerHTML = data.qa_warnings.map(w => '<div>'+w+'</div>').join('');
    }
  } catch (e) {
    errBox.style.display = 'block';
    errBox.textContent = e.toString();
  }
}

renderLists();
</script>
</body>
</html>
"""


def build_input(payload: dict) -> PetitionInput:
    def parse_party_obj(obj: dict) -> Party:
        return Party(
            role=obj.get("role", "davaci"),
            name=obj.get("name", ""),
            tc_id=obj.get("tc_id"),
            address=obj.get("address"),
        )

    if "parties" in payload and isinstance(payload["parties"], list):
        parties = [parse_party_obj(p) for p in payload["parties"] if p.get("name")]
    else:
        parties = []
        for key, role in (("davaci", "davaci"), ("davali", "davali")):
            raw = payload.get(key)
            if not raw:
                continue
            parts = raw.split("|")
            name = parts[0].strip() if parts else ""
            tc = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            addr = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
            parties.append(Party(role=role, name=name, tc_id=tc, address=addr))

    if "facts" in payload and isinstance(payload["facts"], list):
        facts = []
        for f in payload["facts"]:
            summary = f.get("summary", "").strip()
            refs = f.get("evidence_refs", []) or []
            if summary:
                facts.append(Fact(summary=summary, evidence_refs=refs))
    else:
        facts = [Fact(summary=f, evidence_refs=[]) for f in payload.get("facts", []) if f.strip()]

    requests = payload.get("requests") or []
    requests = [r.strip() for r in requests if isinstance(r, str) and r.strip()]
    legal_basis = [b.strip() for b in payload.get("legal_basis", []) if isinstance(b, str) and b.strip()]

    evidence = []
    for ev in payload.get("evidence", []):
        if not isinstance(ev, dict):
            continue
        label = ev.get("label")
        if label:
            evidence.append(Evidence(label=label, description=ev.get("description"), file_id=ev.get("file_id")))
    if not evidence:
        evidence = [
            Evidence(label="Ek-1", description="Sözleşme"),
            Evidence(label="Ek-2", description="Dekont"),
        ]

    return PetitionInput(
        petition_type=payload.get("petition_type", "dava_dilekcesi"),
        court=payload.get("court", ""),
        subject=payload.get("subject", ""),
        parties=parties,
        facts=facts or [Fact(summary="(eksik)", evidence_refs=[])],
        legal_basis=legal_basis,
        requests=requests or ["(eksik)"],
        evidence=evidence,
    )


def make_handler(service: PetitionService):
    class Handler(BaseHTTPRequestHandler):
        def _set_headers(self, status: int = 200, ctype: str = "application/json"):
            self.send_response(status)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
            self.end_headers()

        def do_OPTIONS(self):
            self._set_headers()

        def do_GET(self):
            if self.path == "/health":
                self._set_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            else:
                # Varsayılan: HTML formu döndür
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(HTML_PAGE.encode("utf-8"))

        def do_POST(self):
            if self.path != "/generate":
                self._set_headers(404)
                self.wfile.write(b'{"error":"not found"}')
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = self.rfile.read(length).decode("utf-8")
                payload = json.loads(data or "{}")
                petition_input = build_input(payload)
                output = service.build(petition_input)
                resp = {
                    "text": output.text,
                    "html": output.html,
                    "qa_warnings": output.qa_warnings,
                    "sections": output.sections.model_dump(),
                }
                self._set_headers()
                self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))
            except Exception as exc:  # pragma: no cover
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
                try:
                    print(f"[error] {exc}", flush=True)
                except Exception:
                    pass

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["static", "qwen"], default="static")
    parser.add_argument("--port", type=int, default=9000)
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
    print(f"API http://localhost:{args.port} /generate")
    server.serve_forever()


if __name__ == "__main__":
    main()
