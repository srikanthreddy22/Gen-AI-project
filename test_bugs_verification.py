import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api"

KNOWN_FACTS_TEXT = """
Photosynthesis is the biological process by which green plants, algae, and certain bacteria convert light energy into chemical energy stored in glucose.
The overall chemical equation for oxygenic photosynthesis is 6 CO2 + 6 H2O + light energy -> C6H12O6 + 6 O2.
Photosynthesis takes place within cellular organelles called chloroplasts, which contain chlorophyll, a green pigment that absorbs light primarily in the blue and red wavelengths while reflecting green light.

Photosynthesis occurs in two distinct stages: the light-dependent reactions and the light-independent reactions (also known as the Calvin cycle).
The light-dependent reactions take place within the thylakoid membranes of chloroplasts. During this stage, chlorophyll absorbs photons, exciting electrons that travel through an electron transport chain.
This electron flow drives the photolysis of water molecules, splitting water into oxygen gas, protons, and electrons. The oxygen produced is released into the atmosphere as a byproduct.
The energy released during electron transport powers ATP synthase to produce ATP from ADP and inorganic phosphate, while also reducing NADP+ to NADPH.

The light-independent reactions, or Calvin cycle, take place in the stroma, the fluid-filled space surrounding the thylakoid membranes.
The Calvin cycle utilizes the ATP and NADPH produced during the light reactions to fix atmospheric carbon dioxide into glyceraldehyde-3-phosphate (G3P), a three-carbon sugar precursor to glucose.
The key enzyme responsible for carbon fixation in the Calvin cycle is RuBisCO (ribulose-1,5-bisphosphate carboxylase-oxygenase), which is considered the most abundant enzyme on Earth.
RuBisCO catalyzes the attachment of CO2 to a five-carbon acceptor molecule named ribulose-1,5-bisphosphate (RuBP), yielding unstable six-carbon intermediates that split into 3-phosphoglycerate (3-PGA).

Cellular respiration is the complementary metabolic process in which organisms break down glucose to produce ATP, consuming oxygen and releasing carbon dioxide and water.
Unlike photosynthesis, which is anabolic and endergonic, cellular respiration is catabolic and exergonic.
Glycolysis is the initial step of cellular respiration, occurring in the cytoplasm and generating two molecules of pyruvate from one molecule of glucose without requiring oxygen.
Aerobic respiration continues in the mitochondria through the Krebs cycle and oxidative phosphorylation, yielding up to 36 to 38 ATP molecules per glucose molecule.
"""

def test_full_pipeline():
    print("=" * 60)
    print("STEP 1: Uploading text document to vector store...")
    resp = requests.post(f"{BASE_URL}/upload/text/", json={
        "text": KNOWN_FACTS_TEXT,
        "doc_name": "photosynthesis_cellular_respiration.txt"
    })
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    doc_info = resp.json()
    doc_id = doc_info["doc_id"]
    print(f"Document indexed successfully. doc_id = {doc_id}")
    print(f"Chunks generated: {doc_info.get('chunks', 'N/A')}")

    print("\n" + "=" * 60)
    print("STEP 2: Testing Flashcard Generation (/api/flashcards/)...")
    fc_resp = requests.post(f"{BASE_URL}/flashcards/", json={"doc_id": doc_id, "count": 6})
    assert fc_resp.status_code == 200, f"Flashcards failed: {fc_resp.text}"
    fc_data = fc_resp.json()
    flashcards = fc_data.get("flashcards", [])
    print(f"Generated {len(flashcards)} flashcards:")
    
    assert len(flashcards) >= 4, f"Expected at least 4 flashcards, got {len(flashcards)}"
    seen_fc_questions = set()
    for idx, card in enumerate(flashcards, 1):
        q = card.get("question", "")
        a = card.get("answer", "")
        c_type = card.get("type", "")
        print(f"  [{idx}] Type: {c_type}")
        print(f"       Q: {q}")
        print(f"       A: {a}")
        
        # Quality assertions
        assert len(q) >= 10, f"Question too short: '{q}'"
        assert len(a) >= 15, f"Answer too short: '{a}'"
        assert q not in seen_fc_questions, f"Duplicate flashcard question: '{q}'"
        seen_fc_questions.add(q)
        # Check that answer is a full sentence
        assert any(term in a.lower() for term in ["photosynthesis", "calvin", "chloroplast", "atp", "rubisco", "respiration", "thylakoid", "glucose", "enzyme", "light", "energy"]), \
            f"Flashcard answer not grounded in document text: '{a}'"

    print("[PASS] All flashcard quality assertions PASSED!")

    print("\n" + "=" * 60)
    print("STEP 3: Testing Quiz Generation (/api/quiz/) - 3 Consecutive Rounds...")
    session_questions = []

    for round_num in range(1, 4):
        print(f"\n--- ROUND {round_num} QUIZ GENERATION ---")
        payload = {
            "doc_id": doc_id,
            "count": 5,
            "exclude_questions": session_questions,
            "generation_id": f"test_gen_round_{round_num}"
        }
        q_resp = requests.post(f"{BASE_URL}/quiz/", json=payload)
        assert q_resp.status_code == 200, f"Quiz generation round {round_num} failed: {q_resp.text}"
        q_data = q_resp.json()
        questions = q_data.get("questions", [])
        insufficient = q_data.get("insufficient_material", False)
        print(f"Received {len(questions)} questions (insufficient_material={insufficient}):")

        assert len(questions) > 0, f"No questions returned in round {round_num}"

        round_questions = []
        for q_idx, item in enumerate(questions, 1):
            q_text = item.get("question", "")
            opts = item.get("options", [])
            correct = item.get("correct") or item.get("correct_answer")
            expl = item.get("explanation", "")
            diff = item.get("difficulty", "")

            print(f"  Q{q_idx}: {q_text} [{diff}]")
            print(f"     Options: {opts}")
            print(f"     Correct: {correct}")
            print(f"     Explanation: {expl}")

            # Structure assertions
            assert len(q_text) >= 10, f"Question text too short: '{q_text}'"
            assert len(opts) == 4, f"Options must have exactly 4 items, got {len(opts)}"
            assert correct in opts, f"Correct answer '{correct}' not in options {opts}"
            assert correct is not None and len(str(correct)) > 0, "Missing correct answer"

            # Check for repetition against previously asked questions in earlier rounds!
            for prev_q in session_questions:
                # Basic similarity check
                assert q_text.lower().strip() != prev_q.lower().strip(), \
                    f"CRITICAL BUG: Question '{q_text}' is an exact duplicate of previously asked question '{prev_q}'!"

            round_questions.append(q_text)

        # Append to session history for subsequent rounds
        session_questions.extend(round_questions)
        print(f"[PASS] Round {round_num} passed. Total unique questions asked so far: {len(session_questions)}")

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print(f"Total unique questions verified: {len(session_questions)}")

if __name__ == "__main__":
    test_full_pipeline()
