"""Export the Bloc II Markdown dossier to HTML and PDF."""

from pathlib import Path

from export_bloc1_pdf import build_html, export_pdf, find_chrome


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_PATH = PROJECT_ROOT / "docs" / "bloc2_dossier_v1.md"
CSS_PATH = PROJECT_ROOT / "assets" / "style" / "pharma_pdf.css"
OUTPUT_DIR = PROJECT_ROOT / "dist"
HTML_PATH = OUTPUT_DIR / "bloc2_dossier_v1.html"
PDF_PATH = OUTPUT_DIR / "bloc2_FALIGANT.pdf"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html_text = build_html(
        MARKDOWN_PATH,
        CSS_PATH,
        "Bloc II - Analyse des données pharmaceutiques",
    )
    HTML_PATH.write_text(html_text, encoding="utf-8")

    page_label = "Marc-Alfred FALIGANT - Ynov M2 data Eng - 2026"
    export_pdf(HTML_PATH, PDF_PATH, find_chrome(), page_label)

    print(f"HTML généré : {HTML_PATH}")
    print(f"PDF généré : {PDF_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
