from app.ai_system.ingestion.cleaner import clean_text

def test_clean_text_whitespace_normalization():
    """
    Ensures multiple inline spaces and trailing/leading space are cleaned up.
    """
    raw = "   Intro to   Machine   Learning   "
    assert clean_text(raw) == "Intro to Machine Learning"

def test_clean_text_newline_consolidation():
    """
    Ensures multiple consecutive blank lines are consolidated to a single blank line.
    """
    raw = "Chapter 1\n\n\n\n\nThis is paragraph 1.\n\n\nThis is paragraph 2."
    assert clean_text(raw) == "Chapter 1\n\nThis is paragraph 1.\n\nThis is paragraph 2."

def test_clean_text_line_stripping():
    """
    Ensures each individual line has its start and end spacing stripped.
    """
    raw = "   First Line of Notes   \n   Second Line of Notes   "
    assert clean_text(raw) == "First Line of Notes\nSecond Line of Notes"

def test_clean_text_preserve_headings():
    """
    Ensures Markdown headings and important structures are not destroyed by cleaning.
    """
    raw = "# Lesson 1: Calculus\n\n## Limits\nEvaluate the limit as x approaches infinity.\n"
    cleaned = clean_text(raw)
    assert cleaned == "# Lesson 1: Calculus\n\n## Limits\nEvaluate the limit as x approaches infinity."
