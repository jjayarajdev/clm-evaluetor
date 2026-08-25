"""Small HTTP helpers shared across routers."""

import unicodedata
from urllib.parse import quote


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Build a Content-Disposition header safe for non-ASCII filenames.

    HTTP headers must encode to latin-1; a raw UTF-8 filename (e.g. the
    French "Complétez…N°_.pdf") raises UnicodeEncodeError deep in Starlette
    and 500s the download. Per RFC 5987/6266: an ASCII-fallback `filename=`
    plus the real name in `filename*=UTF-8''…` (all modern browsers prefer
    the latter).
    """
    fallback = (
        unicodedata.normalize("NFKD", filename)
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace('"', "'")
        .replace("\\", "_")
        or "download"
    )
    return (
        f'{disposition}; filename="{fallback}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
