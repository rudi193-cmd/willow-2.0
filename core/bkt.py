#!/usr/bin/env python3
"""
core/bkt.py — Bayesian Knowledge Tracing for skill-mastery estimation.
b17: BKT1  ΔΣ=42

Implements Bayesian Knowledge Tracing (Corbett & Anderson 1995): a two-state
HMM that estimates the latent probability an agent has *mastered* a skill from
a sequence of correct/incorrect outcomes.

Sibling of core/actr.py. Where ACT-R scores an *atom's* retrieval-worthiness
from recency + importance, BKT scores a *skill's* mastery from its outcome
history. Wire it to the outcomes stream (core/outcomes.py terminal states map
to correct/incorrect) to track how well-practised each Fylgja skill or KB topic
is over time, and to know when an agent has crossed a mastery threshold.

Reference implementation: pyBKT (CAHLR, MIT) — https://github.com/CAHLR/pyBKT.
This is a dependency-free reimplementation of the same forward filter + EM fit,
kept lean for Termux / Windows parity (no numpy / pandas / C++ toolchain). The
algorithm is reproduced; no pyBKT source is copied.

Four BKT parameters per skill (plus optional forget):
    prior  (p_L0)  P(mastered before any practice)
    learn  (p_T)   P(unmastered -> mastered) per opportunity
    guess  (p_G)   P(correct | not mastered)
    slip   (p_S)   P(incorrect | mastered)
    forget (p_F)   P(mastered -> unmastered) per opportunity (default 0.0)

Usage:
    from core.bkt import BKTParams, predict_correct, update, trace, fit, evaluate

    p  = BKTParams(prior=0.3, learn=0.2, guess=0.2, slip=0.1)
    pL = p.prior
    pL = update(pL, correct=True, params=p)   # posterior mastery + learning step
    pc = predict_correct(pL, p)               # P(next response correct)

    masteries = trace([1, 0, 1, 1, 1], p)     # forward filter over a sequence
    fitted    = fit([[1, 0, 1, 1, 1],         # EM estimate from many sequences
                     [0, 1, 1, 1, 1]])
    rmse      = evaluate([[1, 0, 1, 1, 1]], fitted, metric="rmse")
"""
from __future__ import annotations

from dataclasses import dataclass

_EPS = 1e-9


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp x into [lo, hi]."""
    return lo if x < lo else hi if x > hi else x


@dataclass
class BKTParams:
    """The four (plus one) BKT parameters for a single skill.

    Values are probabilities, clamped to [0, 1] on construction. ``guess`` and
    ``slip`` are additionally held strictly below 0.5 so the model stays
    identifiable (a learner who guesses or slips more than half the time would
    make mastery and non-mastery indistinguishable).
    """

    prior: float = 0.25
    learn: float = 0.15
    guess: float = 0.20
    slip: float = 0.10
    forget: float = 0.0

    def __post_init__(self) -> None:
        self.prior = _clamp(self.prior)
        self.learn = _clamp(self.learn)
        self.forget = _clamp(self.forget)
        # Identifiability cap: 0 <= guess, slip < 0.5
        self.guess = _clamp(self.guess, 0.0, 0.5 - _EPS)
        self.slip = _clamp(self.slip, 0.0, 0.5 - _EPS)


# ── Forward filtering (inference) ─────────────────────────────────────────────

def predict_correct(p_known: float, params: BKTParams) -> float:
    """P(next response correct) given current P(mastered).

    correct = mastered & no-slip  OR  not-mastered & lucky-guess.
    """
    return p_known * (1.0 - params.slip) + (1.0 - p_known) * params.guess


def _posterior(p_known: float, correct: bool, params: BKTParams) -> float:
    """P(mastered | this observation) via Bayes, *before* the learning step."""
    if correct:
        num = p_known * (1.0 - params.slip)
        den = num + (1.0 - p_known) * params.guess
    else:
        num = p_known * params.slip
        den = num + (1.0 - p_known) * (1.0 - params.guess)
    if den <= _EPS:
        return p_known
    return num / den


def update(p_known: float, correct: bool, params: BKTParams) -> float:
    """Posterior mastery after observing ``correct``, including the learning step.

    Bayes-conditions on the observation, then applies the latent transition:
    an unmastered skill may be learned (``learn``); a mastered one may be
    forgotten (``forget``, default 0).
    """
    cond = _posterior(p_known, bool(correct), params)
    return cond * (1.0 - params.forget) + (1.0 - cond) * params.learn


def trace(responses, params: BKTParams, prior: float | None = None) -> list[float]:
    """Forward filter: P(mastered) *after* each response in ``responses``.

    responses: iterable of 0/1 (or bool/"1"/"0"). prior overrides params.prior.
    Returns one mastery estimate per response, in order.
    """
    p_known = params.prior if prior is None else _clamp(float(prior))
    out: list[float] = []
    for r in responses:
        p_known = update(p_known, bool(int(r)), params)
        out.append(p_known)
    return out


def predict_sequence(responses, params: BKTParams, prior: float | None = None):
    """Standard BKT trace over a sequence.

    Returns (predictions, masteries):
      predictions[t] = P(correct) *before* observing response t (the value used
                       for RMSE / AUC scoring),
      masteries[t]   = P(mastered) *after* observing response t.
    """
    p_known = params.prior if prior is None else _clamp(float(prior))
    preds: list[float] = []
    masteries: list[float] = []
    for r in responses:
        preds.append(predict_correct(p_known, params))
        p_known = update(p_known, bool(int(r)), params)
        masteries.append(p_known)
    return preds, masteries


def mastered(p_known: float, threshold: float = 0.95) -> bool:
    """True once estimated mastery reaches ``threshold`` (Corbett & Anderson use 0.95)."""
    return p_known >= threshold


# ── Parameter fitting (EM / Baum–Welch) ───────────────────────────────────────

def _forward_backward(seq, params: BKTParams):
    """Scaled forward–backward over one observation sequence.

    Returns (gamma, xi):
      gamma[t][i] = P(state_t = i | observations)
      xi[t][i][j] = P(state_t = i, state_{t+1} = j | observations)  for t < T-1
    State 0 = unmastered, state 1 = mastered.
    """
    T = len(seq)
    pi = (1.0 - params.prior, params.prior)
    a = (
        (1.0 - params.learn, params.learn),   # from unmastered
        (params.forget, 1.0 - params.forget),  # from mastered
    )

    def emit(state: int, obs: int) -> float:
        if state == 1:
            return (1.0 - params.slip) if obs == 1 else params.slip
        return params.guess if obs == 1 else (1.0 - params.guess)

    # Forward pass with per-step scaling for numerical stability.
    alpha = [[0.0, 0.0] for _ in range(T)]
    scale = [0.0] * T
    o0 = int(seq[0])
    alpha[0] = [pi[i] * emit(i, o0) for i in range(2)]
    scale[0] = sum(alpha[0]) or _EPS
    alpha[0] = [v / scale[0] for v in alpha[0]]
    for t in range(1, T):
        ot = int(seq[t])
        for j in range(2):
            alpha[t][j] = sum(alpha[t - 1][i] * a[i][j] for i in range(2)) * emit(j, ot)
        scale[t] = sum(alpha[t]) or _EPS
        alpha[t] = [v / scale[t] for v in alpha[t]]

    # Backward pass, reusing the forward scale factors.
    beta = [[0.0, 0.0] for _ in range(T)]
    beta[T - 1] = [1.0 / scale[T - 1], 1.0 / scale[T - 1]]
    for t in range(T - 2, -1, -1):
        ot1 = int(seq[t + 1])
        for i in range(2):
            beta[t][i] = sum(
                a[i][j] * emit(j, ot1) * beta[t + 1][j] for j in range(2)
            ) / scale[t]

    # Posteriors.
    gamma = [[0.0, 0.0] for _ in range(T)]
    for t in range(T):
        g = [alpha[t][i] * beta[t][i] for i in range(2)]
        s = sum(g) or _EPS
        gamma[t] = [v / s for v in g]

    xi = []
    for t in range(T - 1):
        ot1 = int(seq[t + 1])
        m = [[alpha[t][i] * a[i][j] * emit(j, ot1) * beta[t + 1][j]
              for j in range(2)] for i in range(2)]
        s = sum(m[i][j] for i in range(2) for j in range(2)) or _EPS
        xi.append([[m[i][j] / s for j in range(2)] for i in range(2)])

    return gamma, xi


def fit(
    sequences,
    init: BKTParams | None = None,
    max_iter: int = 100,
    tol: float = 1e-5,
    allow_forget: bool = False,
) -> BKTParams:
    """Estimate BKT parameters from observed sequences via EM (Baum–Welch).

    sequences: list of per-opportunity 0/1 outcome sequences for ONE skill
               (one sequence per learner / practice run).
    init:      optional starting params (defaults to a neutral prior).
    allow_forget: if False (default, matching pyBKT), forget is pinned to 0.

    Returns the fitted BKTParams. Empty input returns ``init`` (or defaults).
    """
    seqs = [[int(x) for x in s] for s in sequences if len(s) > 0]
    if not seqs:
        return init or BKTParams()

    p = init or BKTParams()
    for _ in range(max_iter):
        # Expected-count accumulators.
        prior_num = 0.0                     # E[state_1 = mastered]
        trans01_num = trans_from0_den = 0.0  # learn
        trans10_num = trans_from1_den = 0.0  # forget
        guess_num = unmastered_den = 0.0     # P(correct | unmastered)
        slip_num = mastered_den = 0.0        # P(incorrect | mastered)

        for seq in seqs:
            gamma, xi = _forward_backward(seq, p)
            T = len(seq)
            prior_num += gamma[0][1]
            for t in range(T):
                unmastered_den += gamma[t][0]
                mastered_den += gamma[t][1]
                if seq[t] == 1:
                    guess_num += gamma[t][0]
                else:
                    slip_num += gamma[t][1]
            for t in range(T - 1):
                trans_from0_den += gamma[t][0]
                trans_from1_den += gamma[t][1]
                trans01_num += xi[t][0][1]
                trans10_num += xi[t][1][0]

        n = len(seqs)
        new = BKTParams(
            prior=prior_num / n,
            learn=(trans01_num / trans_from0_den) if trans_from0_den > _EPS else p.learn,
            guess=(guess_num / unmastered_den) if unmastered_den > _EPS else p.guess,
            slip=(slip_num / mastered_den) if mastered_den > _EPS else p.slip,
            forget=((trans10_num / trans_from1_den) if (allow_forget and trans_from1_den > _EPS) else 0.0),
        )

        delta = max(
            abs(new.prior - p.prior),
            abs(new.learn - p.learn),
            abs(new.guess - p.guess),
            abs(new.slip - p.slip),
            abs(new.forget - p.forget),
        )
        p = new
        if delta < tol:
            break
    return p


# ── Evaluation ────────────────────────────────────────────────────────────────

def _auc(preds: list[float], labels: list[int]) -> float:
    """Area under the ROC curve via the rank-sum (Mann–Whitney) identity.

    Returns 0.5 when only one class is present (AUC undefined).
    """
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return 0.5
    order = sorted(range(len(preds)), key=lambda i: preds[i])
    ranks = [0.0] * len(preds)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and preds[order[j + 1]] == preds[order[i]]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-based average rank for the tie group
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    rank_sum_pos = sum(ranks[i] for i in range(len(labels)) if labels[i] == 1)
    return (rank_sum_pos - pos * (pos + 1) / 2.0) / (pos * neg)


def evaluate(sequences, params: BKTParams, metric: str = "rmse") -> float:
    """Score BKT predictions against observed outcomes.

    For each opportunity, predict P(correct) *before* seeing the response, then
    compare to the actual 0/1 outcome. Pools all opportunities across sequences.

    metric: "rmse" (default), "accuracy", or "auc".
    """
    preds: list[float] = []
    labels: list[int] = []
    for s in sequences:
        seq = [int(x) for x in s]
        if not seq:
            continue
        p, _ = predict_sequence(seq, params)
        preds.extend(p)
        labels.extend(seq)

    if not labels:
        return 0.0

    m = metric.lower()
    if m == "rmse":
        sse = sum((pr - la) ** 2 for pr, la in zip(preds, labels))
        return (sse / len(labels)) ** 0.5
    if m in ("acc", "accuracy"):
        hits = sum(1 for pr, la in zip(preds, labels) if (pr >= 0.5) == (la == 1))
        return hits / len(labels)
    if m == "auc":
        return _auc(preds, labels)
    raise ValueError(f"unknown metric: {metric!r} (use rmse, accuracy, or auc)")
