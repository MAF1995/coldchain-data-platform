"""Render the Bloc IV Mermaid source files as PNG assets for the editable PPTX."""

import base64
import html
import json
import subprocess
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageChops
import requests
import websocket

from export_bloc1_pdf import ChromePage, find_chrome, find_free_port, wait_for_chrome


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "diagrams"
OUTPUT = SOURCE / "rendered"
DIAGRAMS = [
    "08_bloc4_realtime_relationships",
    "09_bloc4_quality_relationships",
]


def wait_for_mermaid(page: ChromePage) -> None:
    deadline = time.time() + 25
    while time.time() < deadline:
        result = page.command(
            "Runtime.evaluate",
            {
                "expression": "document.body.getAttribute('data-mermaid-rendered') === 'true'",
                "returnByValue": True,
            },
        )
        if result.get("result", {}).get("value") is True:
            return
        time.sleep(0.25)
    raise TimeoutError("Le rendu Mermaid n'a pas terminé à temps.")


def render(diagram_name: str) -> Path:
    definition = (SOURCE / f"{diagram_name}.mmd").read_text(encoding="utf-8")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / f"{diagram_name}.png"
    page_html = f"""<!doctype html>
<html><head><meta charset=\"utf-8\"><style>
html, body {{ margin: 0; width: 1600px; height: 900px; background: #f7fbfb; }}
body {{ display: grid; place-items: center; font-family: Garamond, Georgia, serif; }}
.mermaid {{ width: 1450px; padding: 36px; text-align: center; }}
.mermaid svg {{ width: 100%; height: auto; max-height: 780px; }}
</style></head><body>
<div class=\"mermaid\">{html.escape(definition)}</div>
<script src=\"https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js\"></script>
<script>
mermaid.initialize({{startOnLoad: false, securityLevel: 'loose', theme: 'base'}});
window.addEventListener('load', async () => {{
  await mermaid.run({{querySelector: '.mermaid'}});
  document.body.setAttribute('data-mermaid-rendered', 'true');
}});
</script></body></html>"""
    html_path = OUTPUT / f"{diagram_name}.html"
    html_path.write_text(page_html, encoding="utf-8")

    port = find_free_port()
    with tempfile.TemporaryDirectory(prefix="bloc4_mermaid_", ignore_cleanup_errors=True) as profile_dir:
        process = subprocess.Popen(
            [
                str(find_chrome()),
                "--headless=new",
                "--disable-gpu",
                "--allow-file-access-from-files",
                "--remote-allow-origins=*",
                "--disable-extensions",
                "--no-first-run",
                f"--user-data-dir={profile_dir}",
                f"--remote-debugging-port={port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        page = None
        try:
            wait_for_chrome(port)
            response = requests.put(f"http://127.0.0.1:{port}/json/new", timeout=2)
            response.raise_for_status()
            page = ChromePage(response.json()["webSocketDebuggerUrl"])
            page.command("Page.enable")
            page.command("Runtime.enable")
            page.command("Emulation.setDeviceMetricsOverride", {"width": 1600, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            page.command("Page.navigate", {"url": html_path.resolve().as_uri()})
            wait_for_mermaid(page)
            result = page.command("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
            output_path.write_bytes(base64.b64decode(result["data"]))
            image = Image.open(output_path).convert("RGB")
            background = Image.new("RGB", image.size, (247, 251, 251))
            bbox = ImageChops.difference(image, background).getbbox()
            if bbox:
                left, top, right, bottom = bbox
                padding = 36
                image.crop((max(0, left - padding), max(0, top - padding), min(image.width, right + padding), min(image.height, bottom + padding))).save(output_path)
        finally:
            if page is not None:
                page.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    return output_path


if __name__ == "__main__":
    for name in DIAGRAMS:
        print(f"Diagramme rendu : {render(name)}")
