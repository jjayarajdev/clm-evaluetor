#!/usr/bin/env python3
"""
Convert test contract markdown files to PDF.

Requires: pip install markdown weasyprint
Or use pandoc: brew install pandoc (macOS) / apt install pandoc (Ubuntu)
"""

import os
import subprocess
import sys
from pathlib import Path


def convert_with_pandoc(input_file: Path, output_file: Path) -> bool:
    """Convert markdown to PDF using pandoc."""
    try:
        cmd = [
            "pandoc",
            str(input_file),
            "-o", str(output_file),
            "--pdf-engine=xelatex",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return True
        else:
            print(f"  Pandoc error: {result.stderr}")
            return False
    except FileNotFoundError:
        return False


def convert_with_weasyprint(input_file: Path, output_file: Path) -> bool:
    """Convert markdown to PDF using weasyprint."""
    try:
        import markdown
        from weasyprint import HTML, CSS

        # Read markdown
        with open(input_file, 'r', encoding='utf-8') as f:
            md_content = f.read()

        # Convert to HTML
        html_content = markdown.markdown(
            md_content,
            extensions=['tables', 'fenced_code', 'toc']
        )

        # Wrap in HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; font-size: 11pt; margin: 1in; }}
                h1 {{ color: #333; border-bottom: 2px solid #333; }}
                h2 {{ color: #444; border-bottom: 1px solid #ccc; }}
                h3 {{ color: #555; }}
                table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f5f5f5; }}
                code {{ background-color: #f5f5f5; padding: 2px 4px; }}
                pre {{ background-color: #f5f5f5; padding: 10px; overflow-x: auto; }}
                hr {{ border: none; border-top: 1px solid #ccc; margin: 2em 0; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Convert to PDF
        HTML(string=full_html).write_pdf(str(output_file))
        return True

    except ImportError:
        return False
    except Exception as e:
        print(f"  WeasyPrint error: {e}")
        return False


def main():
    """Main conversion function."""
    script_dir = Path(__file__).parent

    # Find all markdown files except README
    md_files = [f for f in script_dir.glob("*.md") if f.name != "README.md"]

    if not md_files:
        print("No markdown files found to convert.")
        return

    print(f"Found {len(md_files)} markdown files to convert:\n")

    converted = 0
    failed = 0

    for md_file in md_files:
        pdf_file = md_file.with_suffix('.pdf')
        print(f"Converting: {md_file.name}")

        # Try pandoc first
        if convert_with_pandoc(md_file, pdf_file):
            print(f"  ✓ Created: {pdf_file.name} (pandoc)")
            converted += 1
            continue

        # Fall back to weasyprint
        print("  Pandoc not available, trying weasyprint...")
        if convert_with_weasyprint(md_file, pdf_file):
            print(f"  ✓ Created: {pdf_file.name} (weasyprint)")
            converted += 1
            continue

        print(f"  ✗ Failed to convert {md_file.name}")
        failed += 1

    print(f"\n{'='*50}")
    print(f"Conversion complete: {converted} succeeded, {failed} failed")

    if failed > 0:
        print("\nTo install required tools:")
        print("  macOS:  brew install pandoc")
        print("  Ubuntu: sudo apt install pandoc texlive-xetex")
        print("  Python: pip install markdown weasyprint")


if __name__ == "__main__":
    main()
