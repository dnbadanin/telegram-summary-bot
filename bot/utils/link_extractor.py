import re
from urlextract import URLExtract

_extractor = URLExtract()

# Keep only http/https URLs
_SCHEME_RE = re.compile(r"^https?://", re.IGNORECASE)


def extract_links(text: str | None) -> list[str]:
    if not text:
        return []
    return [url for url in _extractor.gen_urls(text) if _SCHEME_RE.match(url)]
