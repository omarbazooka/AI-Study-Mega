class RetrievalError(Exception):
    pass


class VectorSearchError(RetrievalError):
    pass


class KeywordSearchError(RetrievalError):
    pass


class QueryRewriteError(RetrievalError):
    pass


class ContextBuildError(RetrievalError):
    pass
