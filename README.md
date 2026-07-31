# Multi-Agent AI Test Framework

M.Sc thesis project: **A Multi-Agent AI Framework for Automated Software Test Case Generation and Validation from Software Requirements.**

## Problem Statement

Current AI systems generate test cases using a single prompt, often resulting in incomplete coverage, duplicate scenarios, and limited validation. Existing approaches lack collaborative reasoning among specialized agents, leading to reduced software testing quality.

## Objective

Develop a collaborative multi-agent AI framework that improves software test case generation by having specialized agents reason together — analyzing requirements, generating test cases, reviewing and reaching consensus, then checking coverage and quality — instead of relying on a single monolithic prompt.

## Product Flow

```
Login → Create Project → Add User Story → Requirement Analysis →
Generate Test Cases → Reviewer Agent → Consensus Agent →
Coverage Analysis → Quality Evaluation → Manual Review → Export
```

## Status

**Phase 0 complete** — foundation is in place:
- Email/password auth (JWT)
- Project and User Story management (CRUD)
- Full database schema for the whole pipeline (agent executions, versioned
  test cases, debate transcript, coverage/quality reports, exports)
- React UI with the end-to-end pipeline shown as a stepper; stages after
  "Add User Story" are placeholders for the upcoming build phases

The multi-agent stages themselves (requirement analysis, generation, reviewer,
consensus, coverage, quality) are implemented in later phases.

## Tech Stack

- **Backend:** FastAPI, SQLAlchemy, Alembic, SQLite (swappable to Postgres)
- **Frontend:** React + Vite, React Router
- **Auth:** email/password with JWT (bcrypt hashing)
- **AI (later phases):** Anthropic Claude API

## Project Structure

```
multi-agent-ai-test-framework/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + router registration
│   │   ├── config.py          # settings from .env
│   │   ├── database.py        # SQLAlchemy engine/session
│   │   ├── models.py          # full pipeline schema
│   │   ├── auth/              # register/login/me, JWT, hashing
│   │   ├── projects/         # project CRUD
│   │   └── user_stories/     # user story CRUD
│   ├── alembic/              # migrations
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── api/client.js      # fetch wrapper (attaches JWT)
        ├── auth/             # AuthContext, Login, Register
        ├── projects/         # Dashboard, ProjectDetail
        ├── userStories/      # UserStoryDetail (pipeline stepper)
        └── pipeline/stages.js # pipeline stage definitions
```

## Setup

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit JWT_SECRET, ANTHROPIC_API_KEY
alembic upgrade head          # create the SQLite schema
uvicorn app.main:app --reload # serves at http://localhost:8000 (docs at /docs)
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL defaults to http://localhost:8000
npm run dev                   # serves at http://localhost:5173
```

## Author

Maksud Pranto — M.Sc thesis project.
