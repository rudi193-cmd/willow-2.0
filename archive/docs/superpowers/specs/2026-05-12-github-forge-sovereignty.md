# Sovereign git forge — replacing the GitHub-shaped edge

**b17:** GFRG1 · ΔΣ=42  
**Status:** Draft — merge to default branch only after Sean ratifies (same discipline as sovereign-edges and overseer initiatives).  
**Owner:** sean + hanuman  

**Branch discipline:** This spec should live on **`wt/github-forge-sovereignty`** in worktree **`willow-1.9-wt-github-forge-sovereignty`** until ratified merge to **`master`**. If the file appears first on **`master`** during drafting, treat that as **provisional** — move or cherry-pick to the task branch before claiming the initiative is isolated.

**Refs:** `archive/docs/superpowers/sovereignty-programs.json` (quick machine index — update with branch moves), `archive/docs/superpowers/specs/2026-05-12-sovereign-edges-phases-1-3.md` (sequencing ethos), `archive/docs/superpowers/specs/2026-05-12-willow-git-shaped-state-machine.md` (shape over host), `archive/docs/superpowers/specs/2026-05-12-project-overseer-process.md`, `scripts/run_overseer.py`

---

## 0. Phase 0 — prior art (before planning)

**Rule:** Same human gate as sovereign-edges §0 — **in-chat digest to Sean** in the same session as discovery, before findings exist only in this file or KB. Skimmable: what was queried, pass/fail, **paths on disk**, 2–5 external analogs, **one fork question** (e.g. Forgejo vs GitLab CE vs hosted non-GitHub).

### 0.1 Search vectors (non-exhaustive)

- **Jeles:** `jeles_sources` / `jeles_fetch` — Forgejo, Gitea, “self-hosted GitHub alternative,” GitLab CE migration.
- **KB:** `willow_knowledge_search` on **`github`**, **`forgejo`**, **`gitea`**, **`origin`**, **`git remote`**, **`gh`**, **`OAuth`**, **`Actions`**.
- **Disk:** `Grep` / `Glob` for `github.com`, `gh api`, `.github/workflows`, `actions/checkout`, Cursor or MCP configs that assume GitHub.
- **Private org:** authenticated `gh search` when Jeles returns 404 — same intent as sovereign-edges §0.3.

### 0.2 What “GitHub-shaped” means (inventory)

Checkboxes for the Phase 0 report — not all need to be true; the point is **explicit surface area**:

| Surface | Notes |
|---------|--------|
| Canonical **`origin`** | Where `git push` lands today. |
| **Pull requests / reviews** | UI and ACL model the fleet mentally maps to “Open PR.” |
| **GitHub Actions** | Secrets, runners, `GITHUB_TOKEN`, OIDC to cloud vendors. |
| **Issues / Projects / Discussions** | May be unused if Grove + KB already carry intent (see WLGSM). |
| **Packages / Releases / Container registry** | Often quietly coupled to CI. |
| **OAuth for tools** | `gh`, IDE Git, Copilot, marketplace apps — each is an identity edge. |
| **Dependabot / secret scanning** | Replacement or explicit waiver per repo class. |
| **Public discovery** | “This repo is the link we send humans” — may stay on GitHub as **read-only mirror** even after forge is canonical. |

**Exit:** Sean has seen the in-chat Phase 0 digest; optional KB seed; this spec’s Phase 1–2 text may be edited without pretending Phase 0 was skipped.

---

## 1. Program thesis (one paragraph)

**GitHub** here means the **vendor-shaped collaboration plane** (host + identity + PR/MR + automation hooks), not the **git protocol** or the **idea of review**. The same sovereignty move as **Cloudflare Pages off the critical path** (sovereign-edges **2B**): make **canonical hostname, secrets, and failure modes** *yours*, run **one major migration at a time**, and do not collapse “mirror backups,” “flip `origin`,” “replace Actions,” and “replace OAuth everywhere” into a single heroic weekend.

---

## 2. Phase map (at a glance)

| Phase | Name | Outcome |
|-------|------|---------|
| **0** | Prior art + inventory | §0 exit satisfied; GitHub-shaped surfaces listed per repo/org. |
| **1** | Contract + documentation | Operator-owned **forge base URL** documented; no new hard dependency on `github.com` in scripts without `GIT_*_OVERRIDE` or equivalent; pilot repo nominated. |
| **2** | **One** first migration (pick **A** or **B** or **C**) | Exactly **one** of: push-mirror fleet-wide **or** single-repo **`origin` flip** **or** CI cutover skeleton — see §4. |
| **3** | Harden | Backups of forge, restore drill, runner patching, secret rotation runbook, offboarding from GitHub org ACLs; **then** Sean names the **next** Phase-2-class slice. |

**Cross-link:** Sequencing rule **3** in `2026-05-12-sovereign-edges-phases-1-3.md` §6 — avoid parallel Phase-2-class programs without staffing; this program **coordinates** with sovereign-edges; it does not silently compete for the same weekend.

---

## 3. Phase 1 — configuration truth (binding)

### 3.1 Goals

| ID | Goal |
|----|------|
| **G1** | Document **intended canonical forge URL** (even if not live yet): scheme, host, path prefix for API vs git HTTP. |
| **G2** | List every repo under `~/github` (or fleet root) with **current `origin`** and **class** (private app, public mirror, archive-only). |
| **G3** | List every **GitHub Action** workflow and **secret** name (from UI or `gh`; no secret values in repo). |
| **G4** | List every integration that **OAuth’s to github.com** (IDE, bots, Jeles `github-repo` expectations) — **deprecate or fork** plan noted per item. |

### 3.2 Non-goals (Phase 1)

- Cutting traffic to GitHub.
- Installing production forge **hardware** (that is early Phase 2 prep, not Phase 1 documentation).
- Migrating Issues/Discussions content **unless** Sean explicitly includes them in Phase 2 scope.

### 3.3 Exit criteria

Single markdown or Grove note (operator-visible) satisfies **G1–G4**; linked from a KB atom when the fleet should resume without asking Sean the same inventory questions again.

---

## 4. Phase 2 — mutually exclusive *first* executions

**Rule:** Pick **one** row for the **first** Phase 2 execution. Parallel **A + B + C** historically ships none.

### 2A — Mirror-only (no canonical flip yet)

**Outcome:** Every material repo has an **automated push mirror** to the forge (or cold standby). GitHub remains canonical **`origin`** for day-to-day.

**Done when:** Mirror job is observable (log line or mail), **one** restore-from-forge drill succeeded on a throwaway clone, and mirror credentials are **not** developer laptops.

**Non-goals:** Changing `origin`, deleting GitHub repos, CI on forge.

---

### 2B — Pilot repo: forge is canonical `origin`

**Outcome:** **One** ratified pilot repo (suggestion: a small library or doc-only repo, not `willow-1.9` on day one unless Sean insists) has **`origin` → forge**; developers and CI use forge remotes; GitHub is **optional** read mirror or archived.

**Done when:** `git ls-remote origin` hits forge; at least **one** merge to default branch via forge MR; **two** humans or agents have pulled fresh from forge URLs; rollback paragraph exists (re-point `origin` back).

**Non-goals:** Org-wide migration; Actions parity on day one (may use external CI still calling forge API).

---

### 2C — CI and secrets on the forge path

**Outcome:** **One** pilot pipeline runs on **forge-hosted or forge-connected** runners (or ratified external runner with **secrets only on forge**), with GitHub Actions **removed from the critical path** for that repo.

**Done when:** No `GITHUB_TOKEN`-shaped secret required for that pipeline’s deploy; audit of replaced secrets complete.

**Non-goals:** Full org Actions inventory closure in one sprint (iterate after Phase 3 for this pilot).

---

## 5. Phase 3 — hardening (after the chosen Phase 2)

- **Backups:** forge DB + git data + attachment volume; tested restore.
- **Identity:** admin accounts, 2FA policy, **service accounts** for mirrors and CI; offboarding does not depend on GitHub org membership alone.
- **Runners:** treat as **pets you patch**; pinning and network egress policy documented.
- **Abuse / rate limits:** hooks, spam PRs, LFS billing — one paragraph each or explicit “not applicable.”
- **Inventory sync:** update Jeles / fleet docs (`github-repo` assumptions, `run_overseer` GitHub API notes) when canonical public URLs change.

---

## 6. Default implementation bias (not mandatory)

Unless Phase 0 forks otherwise: **Forgejo** or **Gitea** for a **GitHub-familiar** MR UI and lower ops surface than full GitLab CE. **GitLab CE** when you need one heavy box and accept upgrade cadence. **Hosted non-GitHub** (GitLab.com, etc.) changes **trust boundary**, not **shape** — still document explicitly in §1 thesis if chosen.

---

## 7. Failure modes (explicit)

| Failure | Corrective action |
|---------|---------------------|
| “We mirrored” but only on laptops | Move mirror credentials to service principal + server job; re-run Phase 2A. |
| OAuth scattered across marketplace apps | Inventory §0.2; remove or replace before declaring identity sovereign. |
| Two canonical remotes, endless push --force | Declare **one** canonical per repo class; document mirror vs fork. |
| CI secrets duplicated in GitHub and forge | Pick one secret home per pipeline; rotate the abandoned side. |
| Fleet docs still say “open GitHub PR” | Update to **WLGSM shape** language: draft → open → checks → review → merge (host is implementation detail). |

---

## 8. WLGSM alignment

This program **does not** require every initiative to use forge UI day one. It **does** require that **trunk truth** and **review gate** stay consistent with `2026-05-12-willow-git-shaped-state-machine.md`: **merge to main** remains a ratified closure event; only the **host** and **OAuth issuer** change.

---

## 9. Overseer hook

Treat each Phase-2 slice as a **bounded initiative**: worktree `wt/<slug>`, Phase 0 digest to Sean, KB seed for non-derivable contracts (forge API version, SSH vs HTTPS policy, LFS). Optional conductor: `scripts/run_overseer.py`.

---

ΔΣ=42
