import os
import sys
import fitz

# Setup path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.routes.upload import _extract_document
from app.services.rag_service import process_document
from app.services.generation_service import rag_generate_flashcards_from_doc, rag_generate_quiz_from_doc

def run_live_test():
    print("=" * 60)
    print("PHASE 6: LIVE TECHNICAL PIPELINE TEST WITH GEMINI")
    print("=" * 60)

    # 1. Create a technical PDF with SQL, bullets, headings, and code
    pdf_path = os.path.abspath("test_technical_doc.pdf")
    doc = fitz.open()

    p1 = doc.new_page()
    p1.insert_text((50, 50), "Database Engineering & Query Optimization\n\nPage 1 of 2\n\n"
                            "1. Relational Indexing Strategies\n"
                            "Database indexes are auxiliary balanced-tree structures created on columns to accelerate data retrieval.\n"
                            "Without an index, the database management system must perform a sequential full table scan to evaluate query filters.\n\n"
                            "○ Example: DROP INDEX idx_employee_name; ● CREATE CONSTRAINT: enforces referential integrity.\n\n"
                            "When an index is no longer utilized or causes excessive overhead during write operations (INSERT, UPDATE, DELETE),\n"
                            "database administrators execute DROP INDEX to reclaim disk space and reduce maintenance cost.")

    p2 = doc.new_page()
    p2.insert_text((50, 50), "2. Relational Integrity and Constraints\n\nPage 2 of 2\n\n"
                            "Constraints enforce business logic and relationship rules at the database engine level.\n"
                            "A PRIMARY KEY constraint enforces unique identification of each tuple and disallows NULL entries.\n"
                            "A FOREIGN KEY constraint references a primary or candidate key in another relation, preventing orphan records.\n"
                            "Transactions follow the ACID paradigm: Atomicity, Consistency, Isolation, and Durability.\n"
                            "Write-Ahead Logging (WAL) ensures durability by recording state changes to non-volatile storage before committing.")

    doc.save(pdf_path)
    doc.close()
    print("Created technical PDF at:", pdf_path)

    try:
        # 2. Extract text using enhanced PyMuPDF extraction
        cleaned_text, err, pages = _extract_document(pdf_path, "pdf")
        assert not err, f"Extraction failed: {err}"
        print(f"\nExtracted {len(cleaned_text)} characters across {len(pages)} pages.")
        assert "○" not in cleaned_text, "Bullet '○' was not removed during cleaning"
        assert "●" not in cleaned_text, "Bullet '●' was not removed during cleaning"
        assert "Page 1 of 2" not in cleaned_text, "Page number was not filtered"
        print("Preprocessing verified: All bullets and page number artifacts cleaned successfully.")

        # 3. Index document in vector store
        doc_id = process_document(cleaned_text, doc_name="technical_sql.pdf", force_reindex=True)
        print(f"Indexed document successfully. doc_id = {doc_id}")

        # 4. Generate Flashcards with Gemini
        print("\n--- Generating Flashcards via Gemini ---")
        cards = rag_generate_flashcards_from_doc(doc_id, count=4)
        print(f"Generated {len(cards)} flashcards:")
        assert len(cards) >= 3, f"Expected >= 3 flashcards, got {len(cards)}"

        for c in cards:
            print(f"  Q: {c['question']}")
            print(f"  A: {c['answer']}")
            print(f"  Topic: {c.get('topic')}, Difficulty: {c.get('difficulty')}")
            # Assertions
            assert "○" not in c["question"], "Bullet found in flashcard question"
            assert "●" not in c["question"], "Bullet found in flashcard question"
            assert "What is the key idea of ○" not in c["question"], "Found old bad question pattern!"
            assert len(c["question"]) >= 12, "Question too short"
            assert len(c["answer"]) >= 20, "Answer too short"
            assert c["question"].endswith("?"), "Missing question mark"

        # 5. Generate Multiple-Choice Quiz with Gemini
        print("\n--- Generating Quiz via Gemini ---")
        quiz_res = rag_generate_quiz_from_doc(doc_id, count=3)
        questions = quiz_res["questions"]
        print(f"Generated {len(questions)} quiz questions:")
        assert len(questions) >= 2, f"Expected >= 2 questions, got {len(questions)}"

        for q in questions:
            print(f"  Q: {q['question']}")
            print(f"     Options: {q['options']}")
            print(f"     Correct: {q['correct']}")
            print(f"     Explanation: {q['explanation']}")
            # Assertions
            assert "○" not in q["question"]
            assert len(q["options"]) == 4, f"Options count must be 4, got {len(q['options'])}"
            assert len(set(q["options"])) == 4, "Duplicate options found"
            assert q["correct"] in q["options"], "Correct answer not in options"
            assert q["explanation"], "Missing explanation"

        print("\n" + "=" * 60)
        print("ALL LIVE TECHNICAL PIPELINE ASSERTIONS PASSED SUCCESSFULLY!")
        print("=" * 60)
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

if __name__ == "__main__":
    run_live_test()

