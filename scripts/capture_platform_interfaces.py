import argparse
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "assets" / "screenshots" / "bloc4"
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
CHROME_CANDIDATES = (
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
)


def chrome_path() -> Path:
    configured = os.getenv("BROWSER_EXECUTABLE")
    if configured and Path(configured).exists():
        return Path(configured)
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Navigateur Chromium introuvable")


def capture_grafana(page, output_dir: Path) -> None:
    response = page.request.post(
        "http://localhost:3002/login",
        data={
            "user": os.getenv("GRAFANA_USER", "admin"),
            "password": os.getenv("GRAFANA_PASSWORD", "pharma_admin_local_only"),
        },
    )
    if not response.ok:
        raise RuntimeError(f"Connexion Grafana refusée : HTTP {response.status}")
    page.goto(
        "http://localhost:3002/d/pharma-coldchain-pipeline/"
        "chaine-du-froid-supervision-du-pipeline?from=now-30m&to=now&kiosk",
        wait_until="networkidle",
    )
    page.wait_for_timeout(8_000)
    page.screenshot(
        path=output_dir / "01_grafana_pipeline_monitoring.png",
        full_page=False,
    )


def capture_public_page(page, url: str, output: Path) -> None:
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(3_000)
    page.screenshot(path=output, full_page=False)


def capture_airflow(page, output_dir: Path) -> None:
    password = os.getenv("AIRFLOW_PASSWORD")
    if not password:
        raise RuntimeError("AIRFLOW_PASSWORD doit contenir le mot de passe Airflow")
    dag_url = "http://localhost:8088/dags/pharma_cold_chain_daily"
    response = page.request.post(
        "http://localhost:8088/auth/token",
        data={
            "username": os.getenv("AIRFLOW_USER", "admin"),
            "password": password,
        },
    )
    if not response.ok:
        raise RuntimeError(f"Connexion Airflow refusée : HTTP {response.status}")
    token = response.json()["access_token"]
    page.context.add_cookies(
        [{"name": "_token", "value": token, "url": "http://localhost:8088"}]
    )
    page.goto(dag_url, wait_until="domcontentloaded")
    page.wait_for_timeout(8_000)
    page.screenshot(
        path=output_dir / "05_airflow_dag_execution.png",
        full_page=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture les interfaces de preuve du bloc IV.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--scope",
        choices=("observability", "spark", "airflow"),
        required=True,
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=str(chrome_path()),
            headless=True,
            args=["--disable-gpu", "--hide-scrollbars"],
        )
        page = browser.new_page(
            viewport={"width": CAPTURE_WIDTH, "height": CAPTURE_HEIGHT},
            device_scale_factor=1,
        )
        if args.scope == "observability":
            capture_grafana(page, args.output_dir)
            capture_public_page(
                page,
                "http://localhost:9090/targets",
                args.output_dir / "02_prometheus_targets.png",
            )
            capture_public_page(
                page,
                "http://localhost:9090/alerts",
                args.output_dir / "03_prometheus_alerts.png",
            )
        elif args.scope == "spark":
            capture_public_page(
                page,
                "http://localhost:8090",
                args.output_dir / "04_spark_cluster_execution.png",
            )
        else:
            capture_airflow(page, args.output_dir)
        browser.close()


if __name__ == "__main__":
    main()
