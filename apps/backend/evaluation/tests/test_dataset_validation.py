import pytest
import json
import uuid

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
        
        cases.append({
            "test_case_id": f"TC-{i+1:03d}",
            "document_id": str(uuid.uuid4()),
            "document_filename": doc,
            "document_hash": f"hash-{doc}",
            "question": f"Question {i+1} in {lang}?",
            "language": lang,
            "category": category,
            "difficulty": "medium",
            "answerable": is_answerable,
            "expected_behavior": "fallback" if not is_answerable else "answer",
            "reference_answer": "Model reference answer" if is_answerable else None,
            "required_facts": ["fact 1"] if is_answerable else [],
            "reference_contexts": ["source paragraph"] if is_answerable else [],
            "reference_page_numbers": [1] if is_answerable else [],
            "reference_chunk_ids": [str(uuid.uuid4())] if is_answerable else [],
            "cross_lingual": False,
            "review_status": "pending",
            "generation_notes": "mock note"
        })
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
