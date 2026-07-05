import re
import time


class RerankResult:
    def __init__(self, chunks, latency_ms):
        self.chunks = chunks
        self.latency_ms = latency_ms


class RuleBasedReranker:
    def rerank(self, *, chunks, query_terms, filters, limit):
        start = time.perf_counter()
        terms = [term.lower() for term in query_terms if term]
        seen = set()
        ranked = []
        for chunk in chunks:
            fingerprint = re.sub(r"\s+", " ", chunk.text.lower()).strip()[:240]
            duplicate_penalty = 0.20 if fingerprint in seen else 0.0
            seen.add(fingerprint)

            overlap = self.term_overlap(chunk.text, terms) * 0.12
            metadata = self.metadata_boost(chunk, filters) * 0.10
            length_penalty = self.length_penalty(chunk.text)
            score = max(0.0, chunk.score + overlap + metadata - duplicate_penalty - length_penalty)
            ranked.append(chunk.copy(update={"score": round(score, 6)}))

        ranked = sorted(ranked, key=lambda item: item.score, reverse=True)[:limit]
        return RerankResult(ranked, int((time.perf_counter() - start) * 1000))

    def term_overlap(self, text, terms):
        if not terms:
            return 0.0
        lower = text.lower()
        return sum(1 for term in terms if term in lower) / len(terms)

    def metadata_boost(self, chunk, filters):
        boost = 0.0
        if filters.page_number is not None and chunk.page_number == filters.page_number:
            boost += 1.0
        if filters.section_title and filters.section_title.lower() in (chunk.section_title or "").lower():
            boost += 1.0
        if filters.chapter:
            wanted = filters.chapter.lower()
            if wanted in (chunk.section_title or "").lower() or wanted == str(chunk.metadata.get("chapter", "")).lower():
                boost += 1.0
        return min(boost, 1.0)

    def length_penalty(self, text):
        words = len(text.split())
        if words < 12:
            return 0.12
        if words > 900:
            return 0.08
        return 0.0
