# Verification: anti-hallucination check. A claim's quote must really exist in its source text.
import re
import unicodedata

def normalize(text):
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[*_`#>]", "", text)          # ignore markdown symbols
    return re.sub(r"\s+", " ", text).strip()      # ignore spacing / line-break differences

def quote_exists(quote, source_id, page, chunks):
    """True if the quote appears on exactly that source + page."""
    q = normalize(quote)
    if len(q) < 8:  # too short to prove anything
        return False
    return any(c.source_id == source_id and c.page == page and q in normalize(c.text) for c in chunks)

def find_quote_anywhere(quote, chunks):
    """The model sometimes cites the wrong page. Returns the real (source_id, page) or None."""
    q = normalize(quote)
    if len(q) < 8:
        return None
    for c in chunks:
        if q in normalize(c.text):
            return c.source_id, c.page
    return None