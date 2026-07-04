import re

def clean_text(text: str) -> str:
    """
    Cleans raw extracted PDF text. 
    Standardizes whitespace and newlines while preserving formatting like headings and paragraphs.
    """
    if not text:
        return ""

    # Replace carriage returns with standard newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Replace three or more newlines with exactly two (preserving paragraph separations)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple inline spaces and tabs into a single space
    text = re.sub(r"[ \t]+", " ", text)

    # Strip trailing and leading whitespace from individual lines
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)

    # Collapse excessive newlines that might have opened up after stripping lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Filter out unprintable control characters, but keep standard characters, punctuation, and newlines
    cleaned_chars = [char for char in text if char.isprintable() or char in ("\n", "\t")]
    text = "".join(cleaned_chars)

    return text.strip()
