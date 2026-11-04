import json

import app.services.generation_service as generation_service
import app.services.rag_service as rag_service
import app.services.vector_store as vector_store
from app import create_app
from app.services.quiz_gen import _generate_quiz_locally
from app.services.validation_service import validate_quiz


DEEP_LEARNING = (
    "Deep learning is a subset of machine learning that uses multilayered neural networks."
)

NETWORK_NOTES = """
An IP address is a numeric label assigned to a device on a computer network.
DNS is a naming system that translates domain names into IP addresses.
Routing is the process of selecting a path for data to travel across networks.
A firewall is a security system that monitors and controls network traffic according to rules.
"""

DATABASE_NOTES = """
Database normalization is the process of structuring relational tables to reduce duplicated data and improve data integrity.
First normal form is a rule requiring each table cell to contain one atomic value.
A primary key is a column or group of columns that uniquely identifies each row in a table.
A foreign key is a column that references a key in another table.
"""


def _fake_embedding(texts, model=None):
    return [[float((sum(map(ord, text)) + index) % 17 + 1) for index in range(3)] for text in texts]


def test_definition_fallback_asks_a_complete_grounded_question():
    questions = _generate_quiz_locally(DEEP_LEARNING, count=5)

    assert len(questions) == 1
    question = questions[0]
    assert "deep learning" in question["question"].casefold()
    assert question["question"].endswith("?")
    assert not question["question"].startswith("_")
    assert question["correct_answer"] in question["options"]
    assert "subset of machine learning" in question["correct_answer"]
    assert 2 <= len(question["options"]) <= 4
    assert len({option.casefold() for option in question["options"]}) == len(question["options"])
    assert question["explanation"]


def test_network_questions_are_about_networking_not_another_document():
    questions = _generate_quiz_locally(NETWORK_NOTES, count=5)

    assert questions
    concepts = ("ip address", "dns", "routing", "firewall")
    assert all(any(concept in question["question"].casefold() for concept in concepts) for question in questions)
    assert all("deep learning" not in json.dumps(question).casefold() for question in questions)


def test_database_questions_are_grounded_in_normalization_notes():
    questions = _generate_quiz_locally(DATABASE_NOTES, count=5)

    assert questions
    assert any("normalization" in question["question"].casefold() for question in questions)
    assert all("deep learning" not in json.dumps(question).casefold() for question in questions)


def test_insufficient_text_does_not_produce_fabricated_questions():
    assert _generate_quiz_locally("Learning databases can be useful.", count=5) == []


def test_quiz_api_fallback_is_document_specific_and_keeps_existing_response_shape(monkeypatch, tmp_path):
    monkeypatch.setattr(vector_store, "DB_PATH", str(tmp_path / "quiz-test.db"))
    vector_store.init_db()
    monkeypatch.setattr(rag_service, "get_embeddings", _fake_embedding)
    monkeypatch.setattr(
        generation_service,
        "chat_completion",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("LLM unavailable")),
    )

    network_doc_id = rag_service.process_document(NETWORK_NOTES, doc_name="network notes", force_reindex=True)
    database_doc_id = rag_service.process_document(DATABASE_NOTES, doc_name="database notes", force_reindex=True)
    short_doc_id = rag_service.process_document(
        "Learning databases can be useful.",
        doc_name="short notes",
        force_reindex=True,
    )
    client = create_app().test_client()

    network_response = client.post("/api/quiz/", json={"doc_id": network_doc_id, "count": 3})
    database_response = client.post("/api/quiz/", json={"doc_id": database_doc_id, "count": 3})
    short_response = client.post("/api/quiz/", json={"doc_id": short_doc_id, "count": 3})

    assert network_response.status_code == 200
    assert database_response.status_code == 200
    assert short_response.status_code == 200
    network_data = network_response.get_json()
    database_data = database_response.get_json()
    assert {"questions", "count", "doc_id", "generation_id", "generation_method",
            "insufficient_material", "message", "success"} <= network_data.keys()
    assert network_data["generation_method"] == "local-fallback"
    assert network_data["doc_id"] == network_doc_id
    assert database_data["doc_id"] == database_doc_id
    assert network_data["questions"]
    assert database_data["questions"]
    assert all("database normalization" not in json.dumps(question).casefold()
               for question in network_data["questions"])
    assert all("computer network" not in json.dumps(question).casefold()
               for question in database_data["questions"])

    for question in network_data["questions"] + database_data["questions"]:
        assert {"question", "options", "correct", "correct_answer", "explanation"} <= question.keys()
        assert question["correct_answer"] == question["correct"]
        assert question["correct_answer"] in question["options"]

    short_data = short_response.get_json()
    assert short_data["questions"] == []
    assert short_data["insufficient_material"] is True
    assert "not contain enough clear concept statements" in short_data["message"]


def test_validation_rejects_blanks_duplicate_options_and_unsupported_answers():
    source = (
        DEEP_LEARNING
        + " Machine learning is a field that studies algorithms that learn from data."
        + " Neural networks are composed of layers of neurons and activation functions."
    )
    supported_answer = DEEP_LEARNING
    payload = {
        "questions": [
            {
                "question": "_____ definition Deep learning is a subset of machine learning?",
                "options": [supported_answer, "Machine learning", "Neural networks", "A field of study"],
                "correct": supported_answer,
            },
            {
                "question": "Which statement best describes deep learning?",
                "options": [supported_answer, supported_answer.lower(), "Neural networks", "A field of study"],
                "correct": supported_answer,
            },
            {
                "question": "Which statement best describes deep learning?",
                "options": ["An unrelated claim about astronomy", "Machine learning", "Neural networks", "A field of study"],
                "correct": "An unrelated claim about astronomy",
            },
            {
                "question": "Which statement best describes deep learning?",
                "options": [supported_answer, "Machine learning", "Neural networks", "A field of study"],
                "correct": supported_answer,
            },
        ]
    }

    accepted = validate_quiz(payload, count=5, source_text=source)

    assert len(accepted) == 1
    assert accepted[0]["correct_answer"] == supported_answer


def test_quiz_validation_rejects_punctuation_duplicates_and_near_duplicate_options():
    correct = (
        "A neural network learns patterns through multiple hidden layers using weighted connections "
        "to represent complex relationships between input features and target values."
    )
    near_duplicate = correct.replace("target values", "target outputs")
    duplicate_payload = {
        "questions": [{
            "question": "Which statement describes how a neural network learns?",
            "options": [
                correct,
                correct.lower().replace(".", " !"),
                "Clustering groups unlabelled observations according to their similarity.",
                "Regression estimates a continuous value from labelled examples.",
            ],
            "correct": correct,
        }]
    }
    similar_payload = {
        "questions": [{
            "question": "Which statement describes how a neural network learns?",
            "options": [
                correct,
                near_duplicate,
                "Clustering groups unlabelled observations according to their similarity.",
                "Regression estimates a continuous value from labelled examples.",
            ],
            "correct": correct,
        }]
    }

    assert validate_quiz(duplicate_payload, source_text=correct) == []
    assert validate_quiz(similar_payload, source_text=correct) == []


def test_quiz_validation_maps_normalized_correct_answer_to_displayed_option():
    option = "Deep learning uses multilayered neural networks."
    payload = {
        "questions": [{
            "question": "What architecture does deep learning use?",
            "options": [
                option,
                "Clustering groups unlabelled observations by similarity.",
                "Regression predicts a continuous numerical value.",
                "Classification assigns inputs to predefined categories.",
            ],
            "correct": "deep learning uses multilayered neural networks !",
        }]
    }

    accepted = validate_quiz(payload, source_text=option)

    assert len(accepted) == 1
    assert accepted[0]["correct"] == option
    assert accepted[0]["correct_answer"] == option


def test_fallback_respects_previously_asked_questions():
    questions = _generate_quiz_locally(NETWORK_NOTES, count=5)
    exclusions = [question["question"] for question in questions]

    assert _generate_quiz_locally(NETWORK_NOTES, count=5, exclude_questions=exclusions) == []


def test_local_quiz_generator_produces_diverse_document_grounded_questions():
    source = """
    Deep learning is a subset of machine learning that uses multilayered neural networks.
    A convolutional neural network extracts spatial features from images through local receptive fields.
    Backpropagation adjusts network weights by propagating errors backward through the network.
    Transfer learning reuses a pre-trained model on a new task with less data and training time.
    """

    questions = _generate_quiz_locally(source, count=4)

    assert len(questions) >= 3
    assert all(len(question["options"]) == 4 for question in questions)
    assert all(len(set(option.casefold() for option in question["options"])) == 4 for question in questions)
    assert all(any(term in question["question"].casefold() for term in ["deep learning", "convolutional", "backpropagation", "transfer learning"]) for question in questions)


def test_local_flashcard_generator_stays_document_specific_and_not_generic():
    source = """
    Deep learning is a subset of machine learning that uses multilayered neural networks.
    A convolutional neural network extracts spatial features from images through local receptive fields.
    Backpropagation adjusts network weights by propagating errors backward through the network.
    Transfer learning reuses a pre-trained model on a new task with less data and training time.
    """

    cards = generation_service.rag_generate_flashcards_from_doc if False else __import__('app.services.flashcard_gen', fromlist=['_legacy_generate_flashcards'])._legacy_generate_flashcards(source, count=4)

    assert len(cards) >= 3
    assert all(card["question"].lower() not in {"what is this?", "what is data?"} for card in cards)
    assert all(any(term in card["question"].casefold() or term in card["answer"].casefold() for term in ["deep learning", "convolutional", "backpropagation", "transfer learning"]) for card in cards)


def test_validate_quiz_rejects_reused_distractors_across_questions():
    source = (
        "Deep learning is a subset of machine learning that uses multilayered neural networks. "
        "A convolutional neural network extracts spatial features from images through local receptive fields. "
        "Backpropagation adjusts network weights by propagating errors backward through the network. "
        "Transfer learning reuses a pre-trained model on a new task with less data and training time."
    )
    repeated = [
        "Machine learning studies algorithms that learn patterns from data.",
        "A neural network is composed of layers of connected units that transform input features.",
        "Classification assigns inputs to predefined categories based on learned patterns.",
    ]
    payload = {
        "questions": [
            {
                "question": "Which statement best describes deep learning?",
                "options": [
                    "Deep learning is a subset of machine learning that uses multilayered neural networks.",
                    repeated[0],
                    repeated[1],
                    repeated[2],
                ],
                "correct": "Deep learning is a subset of machine learning that uses multilayered neural networks.",
            },
            {
                "question": "What is the main purpose of backpropagation?",
                "options": [
                    "Backpropagation adjusts network weights by propagating errors backward through the network.",
                    repeated[0],
                    repeated[1],
                    repeated[2],
                ],
                "correct": "Backpropagation adjusts network weights by propagating errors backward through the network.",
            },
        ]
    }

    result = validate_quiz(payload, count=5, source_text=source)

    assert len(result) == 1
    assert result[0]["correct_answer"] == "Deep learning is a subset of machine learning that uses multilayered neural networks."
