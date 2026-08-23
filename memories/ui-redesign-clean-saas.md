---
name: ui-redesign-clean-saas
description: "Frontend is being redesigned to a Clean SaaS (light) look, one module at a time"
metadata: 
  node_type: memory
  type: project
  originSessionId: 002ae7a3-c3f4-4716-8731-9b15900f39c5
  modified: 2026-08-06T12:06:05.375Z
---

The user wants the frontend redesigned to a **fresh, simple, easy-to-use, modern "Clean SaaS (light)"** look (Linear/Notion/Vercel feel), replacing the earlier heavy SELISE theme. Work **module by module**, and **ask before starting each next module** (do not batch).

**Why:** the old UI felt "too complex" — dark navy sidebar, big blue gradient hero, and fake thesis scaffolding (Pipeline-readiness scorecard, "Soon" nav, "Build progress", "Phase 1" pill, "Test cases: 0 / Phase 2" stat) that is now outdated since the pipeline is actually built.

**How to apply:**
- Design foundation lives in `frontend/src/index.css` — `:root` tokens: bg `#fafafb`, white surfaces, indigo accent `--accent:#4f46e5`, neutral grays, Inter for all `--font-*`, radius 8–14px, subtle shadows. Old `--blue-*`/`--selise-*` var names are REMAPPED to the accent so un-redesigned screens stay coherent.
- Redesigned styles are appended at the END of index.css under "CLEAN SAAS REDESIGN" / "CLEAN REDESIGN" headers, using NEW prefixed class names (`.app`, `.side`, `.page-head`, `.stat`, `.pcard`, `.mcard`, `.chip*`, `.create-card`, `.crumb`) so older screens keep their old CSS until redesigned. Old shell/dashboard CSS is now dead but left in place — prune later.
- Light app shell: `frontend/src/components/AppShell.jsx` (light sidebar, nav = Home/Projects only, user+logout in footer, NO topbar).

**ALL screens redesigned + verified:** Dashboard, Project (now requirement-centric), Auth (Login/Register — clean centered card; old `AuthBrand.jsx` deleted), and the Requirement/AI workspace (`requirements/RequirementDetail.jsx`) including the §10 export UI (JSON/CSV/MD/XLSX/PDF wired to `api.exportPackage`, verified 200 in-browser). The old pipeline-stepper section was removed as stale scaffolding, so `pipeline/stages.js` is now unused/dead.

**STRUCTURE CHANGE — Modules removed entirely (hierarchy is now Project → Requirement, 2 steps).** Requirements live directly under a project (`Requirement.module_id` is null for new ones; old rows keep their id but modules are ignored). Backend: `app/modules/` deleted, modules_router removed from `main.py`, new project-level endpoints `GET/POST /projects/{id}/requirements` + `/requirements/upload` in `requirements/routes.py`. Frontend: `modules/ModuleDetail.jsx` deleted, module route removed from `App.jsx`, `ProjectDetail.jsx` rewritten to manage requirements directly (composer + requirement cards with per-tab quick-links), `api.listRequirements(projectId)` / `createRequirement(projectId, body)` / `uploadRequirement(projectId, fd)` no longer take a moduleId. The `Module` ORM model + table still exist (left to avoid a migration) but are unused. 16 backend tests pass.

**Workspace is tabbed** (in-page tab bar, `?tab=` in URL): Overview / Test Cases / Review / Coverage / Quality / Export. Overview holds the one-click **Run full pipeline** (analysis→generate→review→coverage→quality). Test Cases uses a spreadsheet-style grid with type filter tabs + expandable rows.

**Left to do (optional polish):** prune the large blocks of now-dead old CSS in index.css (old `.shell/.sidebar/.topbar`, old dashboard `.hero-grid/.quality-card`, old `.auth-wrap/.auth-brand`, `.story-*` workspace, `.stepper`). Kept for now to avoid risk; safe to delete since no component references them.

Feature building is PAUSED during the redesign (export backend is finished incl. PDF fix). See [[thesis-primary-outputs]] and [[build-ui-with-functionality]].
