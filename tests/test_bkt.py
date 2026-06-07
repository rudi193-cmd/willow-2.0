# b17: B47F0  ΔΣ=42
import random

from core.bkt import (
    BKTParams,
    predict_correct,
    update,
    trace,
    predict_sequence,
    mastered,
    fit,
    evaluate,
)


def test_params_clamp_to_valid_range():
    p = BKTParams(prior=2.0, learn=-1.0, guess=0.9, slip=0.9, forget=5.0)
    assert 0.0 <= p.prior <= 1.0
    assert 0.0 <= p.learn <= 1.0
    assert 0.0 <= p.forget <= 1.0
    # guess and slip held strictly below 0.5 for identifiability
    assert p.guess < 0.5
    assert p.slip < 0.5


def test_predict_correct_within_bounds():
    p = BKTParams(prior=0.3, learn=0.2, guess=0.2, slip=0.1)
    # P(correct) lies between the floor (guess) and ceiling (1 - slip)
    assert predict_correct(0.0, p) == p.guess
    assert abs(predict_correct(1.0, p) - (1.0 - p.slip)) < 1e-12
    pc = predict_correct(0.5, p)
    assert p.guess < pc < 1.0 - p.slip


def test_correct_observation_raises_mastery():
    p = BKTParams(prior=0.3, learn=0.1, guess=0.2, slip=0.1)
    after_correct = update(0.3, correct=True, params=p)
    after_wrong = update(0.3, correct=False, params=p)
    assert after_correct > 0.3
    assert after_wrong < after_correct


def test_trace_monotonic_on_all_correct():
    p = BKTParams(prior=0.2, learn=0.2, guess=0.2, slip=0.1)
    masteries = trace([1, 1, 1, 1, 1], p)
    assert len(masteries) == 5
    # mastery should be non-decreasing as correct answers accumulate
    assert all(masteries[i] <= masteries[i + 1] + 1e-12 for i in range(len(masteries) - 1))
    assert masteries[-1] > masteries[0]


def test_predict_sequence_shapes_and_order():
    p = BKTParams(prior=0.3, learn=0.2, guess=0.2, slip=0.1)
    preds, masteries = predict_sequence([1, 0, 1], p)
    assert len(preds) == len(masteries) == 3
    # first prediction uses the prior, before any observation
    assert abs(preds[0] - predict_correct(p.prior, p)) < 1e-12


def test_mastered_threshold():
    assert mastered(0.96)
    assert not mastered(0.94)
    assert mastered(0.8, threshold=0.75)


def test_fit_empty_returns_init():
    init = BKTParams(prior=0.4)
    assert fit([], init=init) is init
    # default when no init supplied
    assert isinstance(fit([]), BKTParams)


def test_fit_recovers_learnable_skill():
    # Synthetic learners who start weak and reliably improve: late opportunities
    # should be predicted as much more likely correct than early ones.
    rng = random.Random(42)
    truth = BKTParams(prior=0.1, learn=0.3, guess=0.2, slip=0.05)
    sequences = []
    for _ in range(200):
        known = rng.random() < truth.prior
        seq = []
        for _ in range(8):
            p_correct = (1 - truth.slip) if known else truth.guess
            seq.append(1 if rng.random() < p_correct else 0)
            if not known and rng.random() < truth.learn:
                known = True
        sequences.append(seq)

    fitted = fit(sequences, max_iter=200)
    # Parameters stay in valid, identifiable ranges.
    assert 0.0 <= fitted.prior <= 1.0
    assert fitted.guess < 0.5 and fitted.slip < 0.5
    # The model learns that mastery grows: P(correct) at opportunity 8 >> at 1.
    early = predict_correct(fitted.prior, fitted)
    pL = fitted.prior
    for _ in range(7):
        pL = update(pL, correct=True, params=fitted)
    late = predict_correct(pL, fitted)
    assert late > early


def test_evaluate_metrics():
    p = BKTParams(prior=0.5, learn=0.2, guess=0.2, slip=0.1)
    seqs = [[1, 1, 1, 1], [0, 1, 1, 1]]
    rmse = evaluate(seqs, p, metric="rmse")
    acc = evaluate(seqs, p, metric="accuracy")
    auc = evaluate(seqs, p, metric="auc")
    assert 0.0 <= rmse <= 1.0
    assert 0.0 <= acc <= 1.0
    assert 0.0 <= auc <= 1.0


def test_evaluate_unknown_metric_raises():
    p = BKTParams()
    try:
        evaluate([[1, 0]], p, metric="nope")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_fit_lowers_rmse_versus_bad_params():
    rng = random.Random(7)
    truth = BKTParams(prior=0.15, learn=0.25, guess=0.15, slip=0.08)
    sequences = []
    for _ in range(150):
        known = rng.random() < truth.prior
        seq = []
        for _ in range(6):
            p_correct = (1 - truth.slip) if known else truth.guess
            seq.append(1 if rng.random() < p_correct else 0)
            if not known and rng.random() < truth.learn:
                known = True
        sequences.append(seq)

    bad = BKTParams(prior=0.9, learn=0.01, guess=0.49, slip=0.49)
    fitted = fit(sequences, max_iter=200)
    assert evaluate(sequences, fitted, "rmse") < evaluate(sequences, bad, "rmse")
