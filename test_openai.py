import argparse
import json
import os
import re
from pathlib import Path

import requests


def _latest_run(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(r"sorgu(\d+)", re.I)
    best = None
    for child in base_dir.iterdir():
        if not child.is_dir():
            continue
        match = pattern.fullmatch(child.name)
        if not match:
            continue
        try:
            idx = int(match.group(1))
        except ValueError:
            continue
        if best is None or idx > best[0]:
            best = (idx, child)
    if best:
        return best[1]
    raise FileNotFoundError(f"{base_dir} içinde sorgu klasörü bulunamadı.")


def _load_docs_from_text(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    docs = []
    i = 0
    header_re = re.compile(r"^---\s*(\d+)\.\s*Karar:\s*(.+?)\s*\((.*?)\)\s*---\s*$")
    esa_re = re.compile(r"^E:\s*(.*?)\s+K:\s*(.*)$")
    while i < len(lines):
        line = lines[i].strip()
        match = header_re.match(line)
        if not match:
            i += 1
            continue
        daire = match.group(2).strip()
        tarih = match.group(3).strip()
        i += 1
        esas = ""
        karar = ""
        if i < len(lines):
            ek = esa_re.match(lines[i].strip())
            if ek:
                esas = ek.group(1).strip()
                karar = ek.group(2).strip()
                i += 1
        kaynak = ""
        if i < len(lines) and lines[i].startswith("Kaynak:"):
            kaynak = lines[i].split("Kaynak:", 1)[-1].strip()
            i += 1
        if i < len(lines) and lines[i].startswith("Metin"):
            i += 1
        text_lines = []
        while i < len(lines) and not lines[i].startswith("---"):
            text_lines.append(lines[i])
            i += 1
        docs.append(
            {
                "daire": daire,
                "tarih": tarih,
                "esas_no": esas,
                "karar_no": karar,
                "kaynak": kaynak,
                "tam_metin": "\n".join(text_lines).strip(),
            }
        )
    return docs


def _call_chatgpt(api_key: str, prompt: str, model: str, temperature: float = 0.1) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise Turkish legal research assistant.",
            },
            {"role": "user", "content": prompt},
        ],
    }
    resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("ChatGPT yanıtı boş döndü.")
    return choices[0].get("message", {}).get("content", "").strip()


def build_prompt(question: str, docs: list[dict], max_docs: int) -> str:
    selected = docs[: max_docs or 1]
    snippets = []
    for idx, doc in enumerate(selected, 1):
        metin = (doc.get("tam_metin") or "").strip()
        snippets.append(
            f"Karar {idx}\n"
            f"Daire: {doc.get('daire') or 'bilinmiyor'}\n"
            f"Tarih: {doc.get('tarih') or 'bilinmiyor'}\n"
            f"Kaynak: {doc.get('kaynak') or 'Yargıtay'}\n"
            f"Esas: {doc.get('esas_no') or 'yok'} | Karar: {doc.get('karar_no') or 'yok'}\n"
            f"Metin: {metin[:2000]}"
        )
    context = "\n\n".join(snippets)
    return (
        "Aşağıdaki karar notlarında yer alan bilgilerden ayrılmadan kullanıcı sorusunu yanıtlayın. Metinde geçmeyen "
        "herhangi bir bilgi için 'kararlarda bu bilgi yok' deyin. Alıntıladığınız her tespit için hangi karar ve daireye "
        "dayandığınızı belirtin; tahmin, çıkarım veya yorum yok. Sonuç Türkçe ve 3-4 paragraf olsun.\n\n"
        f"Soru: {question.strip()}\n\n"
        f"Karar Notları:\n{context}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Kayıtlı Yargıtay sonuçlarını tekrar özetler.")
    parser.add_argument(
        "--runs-dir",
        default="tests/docs",
        help="sorgu klasörlerinin bulunduğu dizin (varsayılan: tests/docs)",
    )
    parser.add_argument(
        "--run",
        help="Belirli bir sorgu klasörü (ör. tests/docs/sorgu001). Boşsa en son klasör seçilir.",
    )
    parser.add_argument("--max-docs", type=int, default=12, help="LLM özetine dahil edilecek karar sayısı.")
    parser.add_argument("--question", help="Analiz edilecek soru. Boş bırakılırsa sizden istenir.")
    parser.add_argument(
        "--output",
        default=None,
        help="Analiz çıktısının yazılacağı dosya (varsayılan run klasöründe analysis_chatgpt.txt).",
    )
    parser.add_argument("--model", default=os.getenv("CHAT_GPT_MODEL", "gpt-4o-mini"), help="Kullanılacak ChatGPT modeli.")
    args = parser.parse_args()

    api_key = os.getenv("CHAT_GPT_API_KEY")
    if not api_key:
        raise EnvironmentError("CHAT_GPT_API_KEY ortam değişkeni bulunamadı.")

    question = args.question
    if not question:
        try:
            question = input("LLM'e sorulacak soruyu girin: ").strip()
        except EOFError:
            question = ""
    if not question:
        raise ValueError("Soru belirtilmedi.")

    runs_dir = Path(args.runs_dir)
    if args.run:
        run_dir = Path(args.run)
    else:
        run_dir = _latest_run(runs_dir)

    docs_txt = run_dir / "docs.txt"
    if not docs_txt.exists():
        raise FileNotFoundError(f"{docs_txt} bulunamadı.")
    docs = _load_docs_from_text(docs_txt)
    if not docs:
        raise RuntimeError(f"{docs_txt} içinde karar bulunamadı.")

    prompt = build_prompt(question, docs, args.max_docs)
    response = _call_chatgpt(api_key, prompt, args.model)

    output_path = Path(args.output) if args.output else run_dir / "analysis_chatgpt.txt"
    output_path.write_text(response, encoding="utf-8")

    metadata = {
        "question": question,
        "run_dir": str(run_dir),
        "max_docs": args.max_docs,
        "model": args.model,
        "output": str(output_path),
    }
    (run_dir / "analysis_chatgpt.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(docs)} karar arasından {min(len(docs), args.max_docs)} adet kullanıldı.")
    print(f"Analiz {output_path} dosyasına kaydedildi.\n")
    print(response)


if __name__ == "__main__":
    main()
