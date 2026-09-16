# Three authoring skills — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `package-content`, `build-projects` and `shapes` into generated packages, so package-authoring knowledge arrives with the package instead of being re-derived per repository.

**Architecture:** Three skill directories under `src/{{ '.claude' }}/skills/`, two of them behind a conditional directory name that drops them for vocabulary packages. A new offline Taskfile task asserts they ship correctly. The rules file, `CLAUDE.md` and `CHANGELOG.md` are updated to match.

**Tech Stack:** Copier 9 with Jinja-templated filenames, Taskfile 3, Claude Code skill format (YAML frontmatter + markdown body, optional `references/` sub-files), Python 3 standard library for the check.

**Spec:** `docs/superpowers/specs/2026-09-16-package-authoring-skills-design.md`

**Prose source:** the spec's *Friction the transcripts show* and *What gets built* sections enumerate every fact each skill must state, with its provenance. This plan does not restate that prose; it fixes paths, frontmatter, section structure and verification. Write the bodies from the spec.

## Global Constraints

- Everything under `src/` is payload; everything else is this repository's tooling. Never conflate them.
- `src/{{ '.claude' }}/` is a quoted expression that renders to `.claude`. Quote these paths in shell commands.
- **A test case renders from `git rev-parse HEAD`.** Commit a `src/` change before expecting it in a rendered case.
- Conditional shipping uses `{% if package_type != 'vocabulary' %}<name>{% endif %}` as the directory name. Verified: the directory is absent entirely in a vocabulary package.
- House style ships as recommended defaults a package may override, and must be marked as such. General rules ship as fact. No package-specific detail is prescribed.
- No skill restates the manifest field reference; `manifest_schema` / `manifest_check` (MCP) are authoritative, the template README is the fallback.
- All commits are signed (`git commit -S`). Work happens on `feature/package-authoring-skills`.
- Do not write a `validate.py`, do not change the scaffolded layout, do not add copier questions.

---

### Task 1: The shipping assertion, written first

**Files:** Modify `Taskfile.yaml`; test by running the new task against both rendered cases.

- [ ] **Step 1: Add `check:skills:case`**, modelled on `check:hook:case`, calling a here-doc Python check that asserts, in `{{.TEST_CASE}}_dir`: every expected `SKILL.md` exists, its frontmatter parses, `name` matches the directory name, no unrendered `{{` or `{%` remains; `template-feedback` and `package-content` are present in both cases; `build-projects` and `shapes` are present only when `.copier-answers.yml` says `package_type: project`, and absent otherwise. Wire it into `check:validate:case` after `check:hook:case`.
- [ ] **Step 2: Run it and watch it fail** — `TEST_CASE=eccenca-testing-project task check:skills:case` reports `package-content` missing.
- [ ] **Step 3: Commit** the task alone, so the red state is in history.

### Task 2: `package-content`

**Files:** Create `src/{{ '.claude' }}/skills/package-content/SKILL.md` (ships to every package).

- [ ] **Step 1: Write the skill** — frontmatter `name: package-content`, description naming its triggers (adding or removing shipped content, a build failing on the manifest, licence questions). Body from the spec: the two-way match and both error messages; the sidecar ritual with `import_into`'s direction; `.DS_Store` and dangling symlinks; path and extension rules; the licence matrix; `package_version` staying `0.0.0`; the symlink arrangement and `DOCUMENTATION.md`; the offline loop and its explicit limitation that `package build` ignores RDF syntax errors. Route to `manifest_schema` / `manifest_check` / `manifest_example` / `package_build_guide` and the template README; restate no field reference.
- [ ] **Step 2: Commit, regenerate both cases, run `check:skills:case`** — both cases now pass the `package-content` assertion and still fail on the two conditional skills.

### Task 3: `build-projects`

**Files:** Create `src/{{ '.claude' }}/skills/{% if package_type != 'vocabulary' %}build-projects{% endif %}/SKILL.md`.

- [ ] **Step 1: Verify the operator and file names against a real export** before writing — read `build/<project-id>/` in `ecc-isms-project-package` and `fearskaper-fame-package` and confirm the task-type directories and operator ids named in the spec.
- [ ] **Step 2: Write the skill** from the spec's build-project material.
- [ ] **Step 3: Commit, regenerate, run the check** — present in the project case, absent in the vocabulary case.

### Task 4: `shapes`

**Files:** Create `src/{{ '.claude' }}/skills/{% if package_type != 'vocabulary' %}shapes{% endif %}/SKILL.md` plus `references/widgets.md`, `references/navigation.md`, `references/validation.md`.

- [ ] **Step 1: Verify every `shui:` predicate spelling against a real shape catalog** — grep `shapes.ttl` in `ecc-isms-project-package` and `fearskaper-fame-package`. A misspelled predicate in a shipped skill is worse than no skill.
- [ ] **Step 2: Write `SKILL.md`** — the model: catalog anatomy, node and property shapes, `rdfs:comment`, property groups (house style, marked overridable), URI templates, read-only and derived fields. Route to the three references.
- [ ] **Step 3: Write the three reference files** — widgets (the WidgetIntegration chain, `_group`, `hideHeader`), navigation (`managedClasses` root-classes-only, navigation lists), validation (strip `shui:inversePath` / `shui:valueQuery`, property coverage).
- [ ] **Step 4: Commit, regenerate, run the check** — expected green for both cases.

### Task 5: Point at them and document

**Files:** Modify `src/{{ '.claude' }}/rules/copier-template.md`, `CLAUDE.md`, `CHANGELOG.md`.

- [ ] **Step 1: Add a paragraph to the rules file** naming the shipped skills, phrased so it stays true in a vocabulary package where two are absent.
- [ ] **Step 2: Extend `CLAUDE.md`** — the anatomy bullet and the feedback section already describe `src/{{ '.claude' }}/`; add what the skills are, that two are conditional, and that `check:skills:case` asserts shipping but not content.
- [ ] **Step 3: Add the changelog entry** under `## [Unreleased]`, extending the existing `.claude/` entry rather than opening a parallel one.
- [ ] **Step 4: Run the full offline suite** — `task check:generate:cases`, then `check:hook:case` and `check:skills:case` for both cases. Report the live half separately; it needs credentials this environment does not have.
- [ ] **Step 5: Commit.**

## After the plan

Merge to `develop` and push; the release that delivers it is a separate, deliberate `/release`.
