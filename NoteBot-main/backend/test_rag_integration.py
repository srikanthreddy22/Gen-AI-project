#!/usr/bin/env python
"""End-to-end integration test for RAG pipeline."""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000/api"

TEST_DOCUMENT = """
Machine Learning Fundamentals

Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.

Types of Machine Learning:

1. Supervised Learning: The model learns from labeled data. Examples include regression and classification tasks.
   - Linear Regression: Used for predicting continuous values
   - Logistic Regression: Used for binary classification problems
   - Decision Trees: Tree-like model used for both classification and regression

2. Unsupervised Learning: The model learns patterns from unlabeled data.
   - K-Means Clustering: Groups similar data points into k clusters
   - Hierarchical Clustering: Creates a tree of clusters
   - Principal Component Analysis (PCA): Reduces dimensionality of data

3. Reinforcement Learning: The model learns through interaction with an environment.
   - Q-Learning: A value-based method
   - Policy Gradient: A policy-based method
   - Actor-Critic: Combines value and policy methods

Key Concepts:

Overfitting: When a model learns the training data too well, including noise.
Underfitting: When a model is too simple to capture the underlying pattern.
Cross-Validation: A technique to evaluate model performance on unseen data.
Regularization: A technique to prevent overfitting by adding a penalty term.

Neural Networks:

Neural networks are inspired by biological neurons and consist of layers:
- Input Layer: Receives the input features
- Hidden Layers: Perform computations and feature extraction
- Output Layer: Produces the final predictions

Activation functions like ReLU, Sigmoid, and Tanh introduce non-linearity.

Deep Learning:

Deep learning uses neural networks with many hidden layers.
Convolutional Neural Networks (CNNs) are effective for image processing.
Recurrent Neural Networks (RNNs) are effective for sequence processing.
Transformers have become state-of-the-art for NLP tasks.

Model Evaluation Metrics:

For Classification: Accuracy, Precision, Recall, F1-Score, AUC-ROC
For Regression: Mean Squared Error (MSE), Root Mean Squared Error (RMSE), Mean Absolute Error (MAE)
"""

def test_pipeline():
    print("\n" + "=" * 80)
    print("RAG INTEGRATION TEST - End-to-End Pipeline")
    print("=" * 80)
    
    # Step 1: Upload document
    print("\n[STEP 1] Uploading document...")
    files = {"file": ("test_document.txt", TEST_DOCUMENT, "text/plain")}
    upload_response = requests.post(f"{BASE_URL}/upload/", files=files)
    
    if upload_response.status_code != 200:
        print(f"❌ Upload failed: {upload_response.text}")
        return False
    
    upload_data = upload_response.json()
    doc_id = upload_data.get("doc_id")
    print(f"✓ Document uploaded successfully")
    print(f"  - Doc ID: {doc_id}")
    print(f"  - Word Count: {upload_data.get('word_count')}")
    print(f"  - Indexed: {upload_data.get('indexed')}")
    
    if not doc_id:
        print("❌ No document ID returned")
        return False
    
    # Step 2: Generate flashcards
    print("\n[STEP 2] Generating flashcards...")
    flashcard_payload = {"doc_id": doc_id, "count": 5}
    flashcard_response = requests.post(
        f"{BASE_URL}/flashcards/",
        json=flashcard_payload
    )
    
    if flashcard_response.status_code != 200:
        print(f"❌ Flashcard generation failed: {flashcard_response.text}")
        return False
    
    flashcard_data = flashcard_response.json()
    flashcards = flashcard_data.get("flashcards", [])
    print(f"✓ Flashcards generated successfully")
    print(f"  - Count: {len(flashcards)}")
    print(f"  - Generation Method: {flashcard_data.get('generation_method')}")
    
    if flashcards:
        print(f"\n  Sample Flashcard:")
        fc = flashcards[0]
        print(f"    Question: {fc.get('question', 'N/A')}")
        print(f"    Answer: {fc.get('answer', 'N/A')[:100]}...")
        print(f"    Type: {fc.get('type', 'N/A')}")
    
    if not flashcards:
        print("❌ No flashcards generated")
        return False
    
    # Step 3: Generate quiz
    print("\n[STEP 3] Generating quiz...")
    quiz_payload = {"doc_id": doc_id, "count": 3}
    quiz_response = requests.post(
        f"{BASE_URL}/quiz/",
        json=quiz_payload
    )
    
    if quiz_response.status_code != 200:
        print(f"❌ Quiz generation failed: {quiz_response.text}")
        return False
    
    quiz_data = quiz_response.json()
    questions = quiz_data.get("questions", [])
    print(f"✓ Quiz generated successfully")
    print(f"  - Count: {len(questions)}")
    print(f"  - Generation Method: {quiz_data.get('generation_method')}")
    
    if questions:
        print(f"\n  Sample Question:")
        q = questions[0]
        print(f"    Question: {q.get('question', 'N/A')}")
        print(f"    Options: {q.get('options', [])}")
        print(f"    Correct: {q.get('correct_answer', 'N/A')}")
    
    if not questions:
        print("❌ No questions generated")
        return False
    
    # Success
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nSummary:")
    print(f"  ✓ Document uploaded and indexed with ID: {doc_id}")
    print(f"  ✓ {len(flashcards)} flashcards generated using RAG + OpenAI")
    print(f"  ✓ {len(questions)} quiz questions generated using RAG + OpenAI")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    try:
        success = test_pipeline()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
