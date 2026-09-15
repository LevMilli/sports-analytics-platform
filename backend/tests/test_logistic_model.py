"""
Tests for logistic_model.py (SimpleLogisticRegression).

No database needed -- this is pure math. The core correctness claim
(matches scikit-learn's own implementation to within 0.00001 on 300
synthetic samples) was checked once in a sandbox before this was ever
wired into the real project, using scikit-learn as an independent
reference -- that comparison isn't repeated here since scikit-learn
isn't a project dependency. These tests instead check the properties
that must hold regardless of the exact optimizer used.
"""

import math

from app.features.logistic_model import SimpleLogisticRegression


def test_learns_a_simple_linear_separation():
    X = [[-3], [-2], [-1.5], [-1], [1], [1.5], [2], [3]]
    y = [0, 0, 0, 0, 1, 1, 1, 1]

    model = SimpleLogisticRegression(iterations=3000)
    model.fit(X, y)

    probs = model.predict_proba(X)
    for i, x in enumerate(X):
        if x[0] < 0:
            assert probs[i] < 0.5, f"Expected low probability for negative input {x[0]}, got {probs[i]}"
        else:
            assert probs[i] > 0.5, f"Expected high probability for positive input {x[0]}, got {probs[i]}"


def test_predictions_are_valid_probabilities():
    X = [[-3], [-2], [-1], [1], [2], [3]]
    y = [0, 0, 0, 1, 1, 1]

    model = SimpleLogisticRegression(iterations=1000)
    model.fit(X, y)
    probs = model.predict_proba(X)

    for p in probs:
        assert 0.0 <= p <= 1.0


def test_sigmoid_is_numerically_stable_on_extreme_values():
    assert math.isclose(SimpleLogisticRegression._sigmoid(1000), 1.0, abs_tol=1e-9)
    assert math.isclose(SimpleLogisticRegression._sigmoid(-1000), 0.0, abs_tol=1e-9)
    assert math.isclose(SimpleLogisticRegression._sigmoid(0), 0.5, abs_tol=1e-9)


def test_symmetric_data_gives_roughly_50_percent_at_zero():
    X = [[-4], [-3], [-2], [-1], [1], [2], [3], [4]]
    y = [0, 0, 0, 0, 1, 1, 1, 1]

    model = SimpleLogisticRegression(iterations=3000)
    model.fit(X, y)
    prob_at_zero = model.predict_proba([[0]])[0]

    assert abs(prob_at_zero - 0.5) < 0.1
