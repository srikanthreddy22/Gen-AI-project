import json
import pytest
from app.routes.upload import clean_extracted_text
from app.services.rag_service import _smart_chunk
from app.services.flashcard_gen import _legacy_generate_flashcards
from app.services.quiz_gen import _generate_quiz_locally
from app.services.validation_service import validate_flashcards, validate_quiz, is_similar_question
import app.services.generation_service as generation_service
from app.services.gemini_service import chat_completion

TECHNICAL_SQL_DOCUMENT = """
Database Indexing and Constraints Guide

○ Example: DROP INDEX idx_employee_name; ● CREATE CONSTRAINT: ensures referential integrity between tables.

Page 1 of 5

1. Introduction to Index Management
Database indexes are auxiliary data structures (typically B-Trees or Hash tables) designed to accelerate query retrieval on selected table columns.
When queries filter or join using a column, an index allows the storage engine to locate matching rows in logarithmic time rather than performing a full table scan.

2. Dropping Indexes
The DROP INDEX statement removes an existing index from a relational database table.
Administrators execute DROP INDEX when an index is redundant, unused by query workloads, or imposing excessive overhead on write operations such as INSERT, UPDATE, and DELETE.
Syntax example: DROP INDEX idx_employee_name ON employees;

3. Table Constraints
Constraints are declarative rules enforced by the relational database management system to ensure data consistency, accuracy, and domain integrity.
A PRIMARY KEY constraint uniquely identifies each record in a table and prevents NULL entries.
A FOREIGN KEY constraint establishes a relational link between two tables, ensuring that values in the child table match existing primary keys in the referenced parent table.
A CHECK constraint validates that values in a column satisfy a Boolean expression before data insertion.
"""


def test_preprocessing_removes_bullets_and_footers_while_preserving_sql():
    cleaned = clean_extracted_text(TECHNICAL_SQL_DOCUMENT)
    # Check that bullet symbols are removed/normalized
    assert "○" not in cleaned
    assert "●" not in cleaned
    # Check that running page numbers / footers are stripped
    assert "Page 1 of 5" not in cleaned
    # Check that SQL commands and concepts are preserved
    assert "DROP INDEX idx_employee_name" in cleaned
    assert "CREATE CONSTRAINT" in cleaned
    assert "PRIMARY KEY constraint" in cleaned
    assert "FOREIGN KEY constraint" in cleaned


def test_chunking_preserves_sql_and_concept_coherence():
    cleaned = clean_extracted_text(TECHNICAL_SQL_DOCUMENT)
    chunks = _smart_chunk(cleaned, chunk_size_chars=500, overlap_chars=100)
    assert len(chunks) >= 2
    # Ensure chunks maintain clean text without split fragments
    for chunk in chunks:
        text = chunk["chunk_text"]
        assert "○" not in text
        assert "●" not in text
        assert len(text) <= 500


def test_flashcard_generation_prevents_bad_bullet_question():
    cards = _legacy_generate_flashcards(TECHNICAL_SQL_DOCUMENT, count=4)
    assert len(cards) >= 2
    for card in cards:
        q = card["question"]
        a = card["answer"]
        # Must never generate the bad question pattern
        assert "What is the key idea of ○" not in q
        assert "●" not in q
        assert "○" not in q
        assert not q.startswith("_")
        assert q.endswith("?")
        assert len(q) >= 12
        assert len(a) >= 15
        assert card["difficulty"] in {"easy", "medium", "hard"}


def test_local_quiz_generates_grounded_sql_mcqs():
    questions = _generate_quiz_locally(TECHNICAL_SQL_DOCUMENT, count=3)
    assert len(questions) >= 2
    for q in questions:
        assert q["question"].endswith("?")
        assert len(q["options"]) == 4
        assert len(set(q["options"])) == 4
        assert q["correct"] in q["options"]
        assert q["correct_answer"] == q["correct"]
        assert "○" not in q["question"]
        assert "●" not in q["question"]
        assert q["explanation"]


def test_validation_rejects_questions_with_broken_fragments_and_bullets():
    bad_data = {
        "flashcards": [
            {
                "question": "What is the key idea of ○ Example: DROP INDEX idx_employee_name; ● CREATE CONSTRAINT?",
                "answer": "Ensures referential integrity between tables.",
                "topic": "SQL",
                "difficulty": "medium",
            },
            {
                "question": "What is the primary function of database indexing?",
                "answer": "It accelerates query retrieval by organizing column pointers in logarithmic structures.",
                "topic": "Indexing",
                "difficulty": "medium",
            }
        ]
    }
    validated = validate_flashcards(bad_data, count=5)
    assert len(validated) == 1
    assert "database indexing" in validated[0]["question"].casefold()

