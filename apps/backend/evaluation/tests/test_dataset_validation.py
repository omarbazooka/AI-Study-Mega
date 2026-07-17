import pytest
import json
import uuid
from evaluation.runners.build_golden_dataset import validate_case, get_jaccard_similarity

@pytest.fixture
def mock_dataset():
    """Generates a valid mock dataset of 30 cases meeting all criteria."""
    cases = []
    # Categories: 10 direct, 5 explain, 5 multi, 3 compare, 3 summary, 4 unanswerable
    categories = (
        ["direct_factual"] * 10 +
        ["explanation"] * 5 +
        ["multi_chunk"] * 5 +
        ["comparison"] * 3 +
        ["summary"] * 3 +
        ["unanswerable"] * 4
    )
    
    # 3 Documents: Doc A, Doc B, Doc C
    docs = ["DocA.pdf", "DocB.pdf", "DocC.pdf"]
    
    # Languages: 15 Arabic, 15 English
    languages = ["ar"] * 15 + ["en"] * 15
    
    for i in range(30):
        category = categories[i]
        lang = languages[i]
        doc = docs[i % 3]
        
        is_answerable = category != "unanswerable"
        
        c = {
            "test_case_id": f"TC-{i+1:03d}",
            "document_id": str(uuid.uuid4()),
            "document_filename": doc,
            "document_hash": f"hash-{doc}",
            "question": f"What is the core concept of topic {i+1} in {lang}?",
            "language": lang,
            "category": category,
            "difficulty": "medium",
            "answerable": is_answerable,
            "expected_behavior": "fallback" if not is_answerable else "answer",
            "reference_answer": "Model reference answer" if is_answerable else None,
            "required_facts": ["fact 1"] if is_answerable else [],
            "reference_contexts": ["source paragraph"] if is_answerable else [],
            "reference_page_numbers": [1] if is_answerable else [],
            "reference_chunk_ids": ["c1", "c2"] if category == "multi_chunk" else ["c1"],
            "cross_lingual": False,
            "review_status": "pending",
            "generation_notes": "mock note"
        }
        if category == "unanswerable":
            c["unanswerable_rationale"] = "Context does not mention topic."
        cases.append(c)
    return cases

def test_case_and_document_count(mock_dataset):
    # Exactly 30 cases
    assert len(mock_dataset) == 30
    
    # Exactly 3 unique documents
    unique_docs = {c["document_filename"] for c in mock_dataset}
    assert len(unique_docs) == 3
    
    # No document has fewer than 8 cases
    for doc in unique_docs:
        doc_cases = [c for c in mock_dataset if c["document_filename"] == doc]
        assert len(doc_cases) >= 8

def test_category_distribution(mock_dataset):
    categories = [c["category"] for c in mock_dataset]
    assert categories.count("direct_factual") == 10
    assert categories.count("explanation") == 5
    assert categories.count("multi_chunk") == 5
    assert categories.count("comparison") == 3
    assert categories.count("summary") == 3
    assert categories.count("unanswerable") == 4

def test_language_minimums(mock_dataset):
    languages = [c["language"] for c in mock_dataset]
    assert languages.count("ar") >= 8
    assert languages.count("en") >= 8

def test_references_for_answerable(mock_dataset):
    for c in mock_dataset:
        if c["answerable"]:
            assert c["reference_answer"] is not None
            assert len(c["required_facts"]) > 0
            assert len(c["reference_contexts"]) > 0
            assert len(c["reference_page_numbers"]) > 0
            assert len(c["reference_chunk_ids"]) > 0
        else:
            assert c["reference_answer"] is None
            assert len(c["required_facts"]) == 0
            assert c["expected_behavior"] == "fallback"

def test_no_duplicate_questions(mock_dataset):
    questions = [c["question"].strip().lower() for c in mock_dataset]
    assert len(questions) == len(set(questions))

def test_validate_case_placeholders():
    # Setup mock chunks
    manifest_chunks = {
        "DocA.pdf": [{"id": "c1"}, {"id": "c2"}]
    }
    
    # Test valid case
    valid_c = {
        "test_case_id": "TC-001",
        "document_filename": "DocA.pdf",
        "question": "What is database RLS?",
        "language": "en",
        "category": "direct_factual",
        "answerable": True,
        "expected_behavior": "answer",
        "reference_answer": "Row Level Security",
        "required_facts": ["RLS restricts row access"],
        "reference_chunk_ids": ["c1"],
        "reference_page_numbers": [1],
    }
    is_ok, reason = validate_case(valid_c, manifest_chunks)
    assert is_ok, f"Expected valid, got: {reason}"

    # Test placeholder question
    placeholder_c = dict(valid_c, question="Question about RLS (template fallback)")
    is_ok, reason = validate_case(placeholder_c, manifest_chunks)
    assert not is_ok
    assert "placeholder" in reason.lower()

    # Test Arabic placeholder
    placeholder_ar = dict(valid_c, question="سؤال حول احتياطي")
    is_ok, reason = validate_case(placeholder_ar, manifest_chunks)
    assert not is_ok
    assert "placeholder" in reason.lower()

    # Test context phrase violation
    phrase_c = dict(valid_c, question="According to the snippet, what is database RLS?")
    is_ok, reason = validate_case(phrase_c, manifest_chunks)
    assert not is_ok
    assert "wording violation" in reason.lower()

    # Test multi-chunk requirement
    multi_c = dict(valid_c, category="multi_chunk", reference_chunk_ids=["c1"])
    is_ok, reason = validate_case(multi_c, manifest_chunks)
    assert not is_ok
    assert "requires at least 2" in reason.lower()

    # Test unanswerable rationale missing
    unans_c = {
        "test_case_id": "TC-002",
        "document_filename": "DocA.pdf",
        "question": "What is Python?",
        "language": "en",
        "category": "unanswerable",
        "answerable": False,
        "expected_behavior": "fallback",
        "reference_answer": None,
        "reference_chunk_ids": [],
    }
    is_ok, reason = validate_case(unans_c, manifest_chunks)
    assert not is_ok
    assert "unanswerable_rationale" in reason.lower()

def test_jaccard_similarity():
    q1 = "what is database row level security?"
    q2 = "what is database row level security"
    q3 = "how do I cook spaghetti at home?"
    
    assert get_jaccard_similarity(q1, q2) > 0.80
    assert get_jaccard_similarity(q1, q3) < 0.20
