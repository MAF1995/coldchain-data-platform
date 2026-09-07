import argparse
import base64
import html
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import markdown
import requests
import websocket


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MD = PROJECT_ROOT / "docs" / "bloc1_dossier_v1.md"
DEFAULT_CSS = PROJECT_ROOT / "assets" / "style" / "pharma_pdf.css"
DEFAULT_OUT_DIR = PROJECT_ROOT / "dist"
DEFAULT_STUDENT_NAME = "Marc-Alfred FALIGANT"
DEFAULT_SCHOOL = "Ynov M2 data Eng"
DEFAULT_YEAR = "2026"


def find_chrome() -> Path:
    candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Chrome ou Edge introuvable pour l'export PDF.")


def render_markdown_fragment(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=["extra", "sane_lists", "tables", "fenced_code", "md_in_html"],
        output_format="html5",
    )


def extract_cover(markdown_text: str) -> tuple[str, dict[str, str]]:
    pattern = re.compile(r'<div class="cover">\s*(.*?)\s*</div>', re.DOTALL)
    blocks: dict[str, str] = {}

    def repl(match: re.Match) -> str:
        key = "@@COVER_BLOCK_0@@"
        inner = render_markdown_fragment(match.group(1).strip())
        blocks[key] = f'<div class="cover">\n{inner}\n</div>'
        return key

    return pattern.sub(repl, markdown_text, count=1), blocks


def extract_mermaid(markdown_text: str) -> tuple[str, dict[str, str]]:
    blocks: dict[str, str] = {}

    def repl(match: re.Match) -> str:
        key = f"@@MERMAID_BLOCK_{len(blocks)}@@"
        diagram = match.group(1).strip()
        blocks[key] = f'<div class="mermaid">\n{html.escape(diagram)}\n</div>'
        return key

    updated = re.sub(r"```mermaid\s+(.*?)```", repl, markdown_text, flags=re.DOTALL)
    return updated, blocks


def restore_mermaid(html_text: str, blocks: dict[str, str]) -> str:
    for key, block in blocks.items():
        html_text = html_text.replace(f"<p>{key}</p>", block)
        html_text = html_text.replace(key, block)
    return html_text


def restore_blocks(html_text: str, blocks: dict[str, str]) -> str:
    for key, block in blocks.items():
        html_text = html_text.replace(f"<p>{key}</p>", block)
        html_text = html_text.replace(key, block)
    return html_text


def build_html(
    md_path: Path,
    css_path: Path,
    document_title: str = "Bloc 1 - Data engineering pharma",
) -> str:
    md_text = md_path.read_text(encoding="utf-8")
    md_text, cover_blocks = extract_cover(md_text)
    md_text, mermaid_blocks = extract_mermaid(md_text)
    body = render_markdown_fragment(md_text)
    body = restore_blocks(body, cover_blocks)
    body = restore_mermaid(body, mermaid_blocks)
    css = css_path.read_text(encoding="utf-8")
    md_base_uri = md_path.parent.resolve().as_uri() + "/"

    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="{html.escape(md_base_uri)}">
  <title>{html.escape(document_title)}</title>
  <style>
{css}

body {{
  max-width: 190mm;
  margin: 0 auto;
}}

.mermaid {{
  background: #f5fbfb;
  border: 1px solid var(--line);
  border-radius: 9px;
  padding: 10px;
  margin: 12px 0 16px;
}}

@media print {{
  @page {{
    margin: 15mm 12mm 15mm 12mm;
  }}
  body {{
    max-width: none;
    margin: 0;
  }}
  .mermaid {{
    break-inside: avoid;
  }}
  pre,
  table,
  blockquote {{
    break-inside: avoid;
  }}
}}
  </style>
</head>
<body>
{body}
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{
    startOnLoad: false,
    securityLevel: "loose",
    theme: "base"
  }});
  window.addEventListener("load", async () => {{
    await mermaid.run({{ querySelector: ".mermaid" }});
    document.body.setAttribute("data-mermaid-rendered", "true");
  }});
</script>
</body>
</html>
"""


class ChromePage:
    def __init__(self, websocket_url: str) -> None:
        self.ws = websocket.create_connection(websocket_url, timeout=30)
        self.message_id = 0

    def close(self) -> None:
        self.ws.close()

    def command(self, method: str, params: dict | None = None) -> dict:
        self.message_id += 1
        payload = {"id": self.message_id, "method": method, "params": params or {}}
        self.ws.send(json.dumps(payload))

        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") != self.message_id:
                continue
            if "error" in message:
                raise RuntimeError(f"Chrome CDP error on {method}: {message['error']}")
            return message.get("result", {})


def find_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_chrome(port: int) -> None:
    deadline = time.time() + 15
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=0.5)
            if response.ok:
                return
        except requests.RequestException:
            time.sleep(0.2)
    raise TimeoutError("Chrome n'a pas ouvert le port de débogage à temps.")


def wait_for_render(page: ChromePage) -> None:
    deadline = time.time() + 25
    expression = (
        "document.readyState === 'complete' && "
        "document.body.getAttribute('data-mermaid-rendered') === 'true'"
    )
    while time.time() < deadline:
        result = page.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        if result.get("result", {}).get("value") is True:
            return
        time.sleep(0.35)
    raise TimeoutError("Le rendu HTML/Mermaid n'a pas terminé avant l'export PDF.")


def build_page_template(page_label: str, align: str) -> str:
    return (
        '<div style="width:100%;'
        f'text-align:{align};'
        'font-family:Garamond, Georgia, serif;'
        'font-size:8px;'
        'color:#557a80;'
        'padding:0 14mm;">'
        f"{html.escape(page_label)}"
        "</div>"
    )


def export_pdf(html_path: Path, pdf_path: Path, chrome_path: Path, page_label: str) -> None:
    port = find_free_port()
    with tempfile.TemporaryDirectory(prefix="bloc1_chrome_", ignore_cleanup_errors=True) as profile_dir:
        process = subprocess.Popen(
            [
                str(chrome_path),
                "--headless=new",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--remote-allow-origins=*",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile_dir}",
                f"--remote-debugging-port={port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        page = None
        try:
            wait_for_chrome(port)
            response = requests.put(
                f"http://127.0.0.1:{port}/json/new",
                timeout=2,
            )
            response.raise_for_status()
            target = response.json()

            page = ChromePage(target["webSocketDebuggerUrl"])
            page.command("Page.enable")
            page.command("Runtime.enable")
            page.command(
                "Page.navigate",
                {"url": html_path.resolve().as_uri()},
            )
            wait_for_render(page)
            page.command("Emulation.setEmulatedMedia", {"media": "print"})
            pdf_result = page.command(
                "Page.printToPDF",
                {
                    "printBackground": True,
                    "displayHeaderFooter": True,
                    "headerTemplate": build_page_template(page_label, "right"),
                    "footerTemplate": build_page_template(page_label, "center"),
                    "preferCSSPageSize": True,
                },
            )
            pdf_path.write_bytes(base64.b64decode(pdf_result["data"]))
        finally:
            if page is not None:
                page.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporte le dossier Bloc 1 Markdown en HTML puis PDF.")
    parser.add_argument("--md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--css", type=Path, default=DEFAULT_CSS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--student-name", default=DEFAULT_STUDENT_NAME)
    parser.add_argument("--school", default=DEFAULT_SCHOOL)
    parser.add_argument("--year", default=DEFAULT_YEAR)
    parser.add_argument("--no-pdf", action="store_true", help="Génère seulement le HTML.")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    html_path = args.out_dir / "bloc1_dossier_v1.html"
    pdf_path = args.out_dir / "bloc1_dossier_v1.pdf"

    page_label = f"{args.student_name} - {args.school} - {args.year}"
    html_text = build_html(args.md, args.css)
    html_path.write_text(html_text, encoding="utf-8")
    print(f"HTML généré: {html_path}")

    if not args.no_pdf:
        chrome_path = find_chrome()
        export_pdf(html_path, pdf_path, chrome_path, page_label)
        print(f"PDF généré: {pdf_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
