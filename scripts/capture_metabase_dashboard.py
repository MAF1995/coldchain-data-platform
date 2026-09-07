"""Capture the authenticated Bloc II Metabase dashboard as a PNG evidence file."""

from __future__ import annotations

import argparse
import base64
import os
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from export_bloc1_pdf import ChromePage, find_chrome, find_free_port, wait_for_chrome


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "assets" / "screenshots" / "bloc2" / "06_metabase_dashboard.png"
)


def wait_for_dashboard(page: ChromePage) -> None:
    expression = """
        (() => {
          const text = document.body ? document.body.innerText : '';
          const ready = document.readyState === 'complete';
          const hasTitle = text.includes('Bloc II - Analyse qualité');
          const hasCards = text.includes('Conformité thermique globale')
            && text.includes('Détail des mesures hors plage');
          const loading = text.includes('Chargement…') || text.includes('Loading…');
          return ready && hasTitle && hasCards && !loading;
        })()
    """
    deadline = time.time() + 75
    while time.time() < deadline:
        result = page.command(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        if result.get("result", {}).get("value") is True:
            time.sleep(3)
            return
        time.sleep(0.75)
    state = page.command(
        "Runtime.evaluate",
        {
            "expression": "location.href + '\\n---\\n' + (document.body ? document.body.innerText : '')",
            "returnByValue": True,
        },
    )
    detail = state.get("result", {}).get("value", "état DOM indisponible")[:1200]
    raise TimeoutError(f"Le dashboard Metabase n'a pas terminé son rendu.\n{detail}")


def capture(
    base_url: str,
    dashboard_id: int,
    email: str,
    password: str,
    output_path: Path,
) -> None:
    login = requests.post(
        f"{base_url.rstrip('/')}/api/session",
        json={"username": email, "password": password},
        timeout=30,
    )
    login.raise_for_status()
    session_id = login.json()["id"]

    chrome_path = find_chrome()
    port = find_free_port()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="metabase_capture_", ignore_cleanup_errors=True) as profile:
        process = subprocess.Popen(
            [
                str(chrome_path),
                "--headless=new",
                "--disable-gpu",
                "--remote-allow-origins=*",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                "--window-size=1920,900",
                f"--user-data-dir={profile}",
                f"--remote-debugging-port={port}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        page = None
        try:
            wait_for_chrome(port)
            target = requests.put(
                f"http://127.0.0.1:{port}/json/new",
                timeout=2,
            ).json()
            page = ChromePage(target["webSocketDebuggerUrl"])
            page.command("Page.enable")
            page.command("Runtime.enable")
            page.command("Network.enable")
            page.command(
                "Emulation.setDeviceMetricsOverride",
                {
                    "width": 1920,
                    "height": 900,
                    "deviceScaleFactor": 1,
                    "mobile": False,
                },
            )
            page.command(
                "Network.setCookie",
                {
                    "name": "metabase.SESSION",
                    "value": session_id,
                    "url": base_url,
                    "httpOnly": True,
                    "sameSite": "Lax",
                },
            )
            page.command(
                "Page.navigate",
                {"url": f"{base_url.rstrip('/')}/dashboard/{dashboard_id}"},
            )
            wait_for_dashboard(page)
            page.command(
                "Runtime.evaluate",
                {
                    "expression": (
                        "document.documentElement.style.setProperty('zoom','0.82');"
                        "window.scrollTo(0,0);"
                    )
                },
            )
            time.sleep(2)
            screenshot = page.command(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "fromSurface": True,
                    "captureBeyondViewport": False,
                    "clip": {
                        "x": 490,
                        "y": 50,
                        "width": 940,
                        "height": 760,
                        "scale": 1,
                    },
                },
            )
            output_path.write_bytes(base64.b64decode(screenshot["data"]))
        finally:
            if page is not None:
                page.close()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("METABASE_URL", "http://localhost:3001"),
    )
    parser.add_argument("--dashboard-id", type=int, default=2)
    parser.add_argument(
        "--email",
        default=os.getenv("METABASE_ADMIN_EMAIL", "admin@pharma-analytics.internal"),
    )
    parser.add_argument("--password", default=os.getenv("METABASE_ADMIN_PASSWORD"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not args.password:
        parser.error("Définissez METABASE_ADMIN_PASSWORD ou utilisez --password.")
    capture(args.url, args.dashboard_id, args.email, args.password, args.output)
    print(f"Capture générée : {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
