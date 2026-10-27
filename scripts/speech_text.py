"""Convert display Markdown to plain speech; never alter the saved original."""
import html
import re

def for_speech(value):
    text = html.unescape(str(value or ''))
    text = re.sub(r"\\([\\`*_{}\[\]()#+.!<>-])", r"\1", text)
    # Keep human link labels, omit destinations and tracking parameters.
    text = re.sub(r"!?\[([^\]]*)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"https?://[^\s<>]+", "", text, flags=re.I)
    text = re.sub(r"www\.[^\s<>]+", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"(?m)^\s{0,3}(?:#{1,6}\s*|>\s*|[-+*]\s+)", "", text)
    text = re.sub(r"(?m)^\s*[-*_]{3,}\s*$", "", text)
    text = text.replace('*', '').replace('`', '').replace('\\', '')
    text = re.sub(r"(?<!\w)_+|_+(?!\w)", "", text)
    text = text.replace('|', '. ')
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()
