import time
from .retrieval_errors import ContextBuildError
from .schemas import Citation


class ContextBuildResult:
    def __init__(self, chunks, context_text, citations, latency_ms):
        self.chunks = chunks
        self.context_text = context_text
        self.citations = citations
        self.latency_ms = latency_ms


class ContextBuilder:
    def build(self, *, chunks, max_context_tokens):
        start = time.perf_counter()
        try:
            selected = []
            citations = []
            blocks = []
            used = 0

            for chunk in chunks:
                block = self.format_chunk(chunk)
                tokens = self.estimate_tokens(block)

                if selected and used + tokens > max_context_tokens:
                    continue
                if tokens > max_context_tokens:
                    block = self.truncate(block, max_context_tokens - used)
                    tokens = self.estimate_tokens(block)
                if tokens <= 0:
                    continue

                selected.append(chunk)
                citations.append(Citation(
                    chunk_id=chunk.chunk_id,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                ))
                blocks.append(block)
                used += tokens

            return ContextBuildResult(selected, "\n\n".join(blocks), citations, int((time.perf_counter() - start) * 1000))
        except Exception as exc:
            raise ContextBuildError(str(exc)) from exc

    def format_chunk(self, chunk):
        page = chunk.page_number if chunk.page_number is not None else "unknown"
        section = chunk.section_title or "unknown"
        return f"[Chunk ID: {chunk.chunk_id} | Page: {page} | Section: {section} | Score: {chunk.score:.2f}]\n{chunk.text.strip()}"

    def estimate_tokens(self, text):
        return max(1, int(len(text.split()) * 1.3))

    def truncate(self, text, token_budget):
        if token_budget <= 0:
            return ""
        return " ".join(text.split()[: max(1, int(token_budget / 1.3))])
