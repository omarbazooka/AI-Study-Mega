import re
from .schemas import MetadataFilters, QueryRewriteResult
from .retrieval_errors import QueryRewriteError

ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
PUNCT = re.compile(r"[^\w\s\u0600-\u06ff]", re.UNICODE)
SPACE = re.compile(r"\s+")
ARABIC_DIGITS = str.maketrans("".join(chr(0x0660 + i) for i in range(10)), "0123456789")

STOPWORDS = {
    "a", "an", "the", "about", "on", "in", "of", "to", "for", "and", "or", "is", "are",
    "Ø§Ø´Ø±Ø­", "Ø´Ø±Ø­", "Ø§Ø¹Ù…Ù„", "Ø³ÙˆÙŠ", "Ø¹Ù†", "ÙÙŠ", "Ù…Ù†", "Ø¹Ù„Ù‰", "Ù…Ø§", "Ù‡Ùˆ", "Ù‡ÙŠ", "Ùˆ", "Ø§Ù„",
}

INTENTS = {
    "quiz": re.compile(r"\b(quiz|test|questions|mcq)\b|" + chr(0x0627) + chr(0x062e) + chr(0x062a) + chr(0x0628) + chr(0x0627) + chr(0x0631), re.I),
    "summary": re.compile(r"\b(summary|summarize)\b|" + chr(0x0645) + chr(0x0644) + chr(0x062e) + chr(0x0635), re.I),
    "explain": re.compile(r"\b(explain)\b|" + chr(0x0634) + chr(0x0631) + chr(0x062d) + "|" + chr(0x0627) + chr(0x0634) + chr(0x0631) + chr(0x062d), re.I),
}

PAGE = re.compile(r"(?:page|p\.?|ØµÙØ­Ø©|Øµ)\s*[:#-]?\s*(\d+)", re.I)
CHAPTER = re.compile(r"(?:chapter|ch\.?|Ø§Ù„ÙØµÙ„|ÙØµÙ„|Ø¨Ø§Ø¨)\s*[:#-]?\s*([\w\u0600-\u06ff-]+)", re.I)
SECTION = re.compile(r"(?:section|Ù‚Ø³Ù…|Ø¬Ø²Ø¡|Ø¹Ù†ÙˆØ§Ù†)\s*[:#-]?\s*([\w\u0600-\u06ff\s-]{1,60})", re.I)


class QueryRewriter:
    def rewrite(self, query: str, intent=None, filters=None) -> QueryRewriteResult:
        try:
            original = query.strip()
            normalized = self.normalize(original)
            extracted = self.extract_filters(normalized)
            merged = self.merge_filters(extracted, filters)
            intent_hint = intent or self.detect_intent(normalized)
            keywords = self.extract_keywords(normalized)
            semantic_query = self.semantic_query(normalized, intent_hint, keywords, merged)
            keyword_query = self.keyword_query(keywords, merged)
            return QueryRewriteResult(
                original_query=original,
                normalized_query=normalized,
                semantic_query=semantic_query,
                keyword_query=keyword_query,
                keywords=keywords,
                filters=merged,
                intent_hint=intent_hint,
            )
        except Exception as exc:
            raise QueryRewriteError(str(exc)) from exc

    def normalize(self, text: str) -> str:
        text = text.translate(ARABIC_DIGITS)
        text = ARABIC_DIACRITICS.sub("", text)
        text = PUNCT.sub(" ", text)
        return SPACE.sub(" ", text).strip()

    def detect_intent(self, text: str):
        for intent, pattern in INTENTS.items():
            if pattern.search(text):
                return intent
        return None

    def extract_filters(self, text: str) -> MetadataFilters:
        page_number = None
        page = PAGE.search(text)
        if page:
            page_number = int(page.group(1))

        chapter = None
        section_title = None
        chapter_match = CHAPTER.search(text)
        if chapter_match:
            chapter = chapter_match.group(1).strip()
            section_title = f"chapter {chapter}"

        section = SECTION.search(text)
        if section and not section_title:
            section_title = section.group(1).strip()

        extra = {}
        # Rule-based difficulty extraction
        diff_match = re.search(r"\b(beginner|easy|مبتدئ|سهل|intermediate|medium|متوسط|advanced|hard|متقدم|صعب)\b", text, re.I)
        if diff_match:
            val = diff_match.group(1).lower()
            if val in ("beginner", "easy", "مبتدئ", "سهل"):
                extra["difficulty"] = "beginner"
            elif val in ("intermediate", "medium", "متوسط"):
                extra["difficulty"] = "intermediate"
            elif val in ("advanced", "hard", "متقدم", "صعب"):
                extra["difficulty"] = "advanced"

        # Rule-based question count extraction
        q_match = re.search(r"(\d+)\s*(?:questions?|أسئلة|سؤال)", text, re.I)
        if q_match:
            extra["question_count"] = int(q_match.group(1))

        # Rule-based language extraction
        lang_match = re.search(r"\b(arabic|ar|عربي|العربية|english|en|إنجليزي|إنجليزية)\b", text, re.I)
        if lang_match:
            val = lang_match.group(1).lower()
            if val in ("arabic", "ar", "عربي", "العربية"):
                extra["language"] = "ar"
            elif val in ("english", "en", "إنجليزي", "إنجليزية"):
                extra["language"] = "en"

        return MetadataFilters(page_number=page_number, chapter=chapter, section_title=section_title, extra=extra)

    def merge_filters(self, extracted, provided):
        if provided is None:
            return extracted
        return MetadataFilters(
            page_number=provided.page_number if provided.page_number is not None else extracted.page_number,
            chapter=provided.chapter or extracted.chapter,
            section_title=provided.section_title or extracted.section_title,
            intent_hint=provided.intent_hint or extracted.intent_hint,
            extra={**extracted.extra, **provided.extra},
        )

    def extract_keywords(self, text: str):
        output = []
        for word in text.lower().split():
            if len(word) >= 2 and word not in STOPWORDS and word not in output:
                output.append(word)
        return output

    def semantic_query(self, normalized, intent, keywords, filters):
        parts = list(keywords) or [normalized]
        if intent == "quiz":
            parts += ["definitions", "key terms", "concepts"]
        elif intent == "summary":
            parts += ["main ideas", "summary"]
        elif intent == "explain":
            parts += ["key concepts", "explanation"]
        if filters.section_title:
            parts.append(filters.section_title)
        return " ".join(dict.fromkeys([p for p in parts if p])).strip()

    def keyword_query(self, keywords, filters):
        parts = list(keywords)
        if filters.section_title:
            parts.append(filters.section_title)
        if filters.page_number is not None:
            parts.append(str(filters.page_number))
        return " ".join(dict.fromkeys([p for p in parts if p])).strip()
