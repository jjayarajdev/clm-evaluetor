"""Regression tests for non-ASCII download filenames.

The French contract "Complétez_avec_Docusign _BON_DE_COMMANDE_N°_.pdf"
500ed on download: its UTF-8 name went verbatim into Content-Disposition,
which Starlette must encode to latin-1. content_disposition() emits an
ASCII fallback plus RFC 5987 filename*.
"""

from app.core.http import content_disposition


class TestContentDisposition:
    def test_ascii_name_passthrough(self):
        header = content_disposition("contract.pdf")
        assert 'filename="contract.pdf"' in header
        assert header.encode("latin-1")  # must be header-safe

    def test_french_accents_and_degree_sign(self):
        name = "Complétez_avec_Docusign _BON_DE_COMMANDE_N°_.pdf"
        header = content_disposition(name)
        header.encode("latin-1")  # the original bug: UnicodeEncodeError here
        assert "filename*=UTF-8''Compl%C3%A9tez" in header
        # NFKD fallback keeps the skeleton readable
        assert 'filename="Completez' in header

    def test_inline_disposition(self):
        header = content_disposition("café.pdf", "inline")
        assert header.startswith("inline; ")
        header.encode("latin-1")

    def test_fully_non_ascii_name_gets_fallback(self):
        header = content_disposition("契約書.pdf")
        assert 'filename=".pdf"' in header or 'filename="download"' in header
        header.encode("latin-1")

    def test_quotes_sanitized_in_fallback(self):
        header = content_disposition('evil"name".pdf')
        # fallback must not break out of the quoted-string
        fallback = header.split('filename="', 1)[1].split('"', 1)[0]
        assert '"' not in fallback
        assert fallback == "evil'name'.pdf"
