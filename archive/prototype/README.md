# Archive — Prototype Recruiter Application

This directory contains the original recruiter-facing web application prototype built before the official RedRob competition dataset was released. It is kept here as development history.

## What is here

`backend/` contains the prototype backend server (`main.py`, FastAPI), which powered a full recruiter workflow tool: resume upload, hybrid retrieval (BM25 + embeddings + ChromaDB), Groq-powered reasoning synthesis, SQLite job/ranking storage, and a Next.js frontend.

This prototype **does not use** the competition ranking pipeline (`backend/competition/rank.py`) and was not submitted as part of the competition solution. The two systems have completely separate code paths.

## Why it is here

We keep it as evidence of:
- The broader problem-solving approach (understanding recruiter needs before the hackathon)
- The early signal extraction and reasoning systems that informed the competition design
- Real engineering iteration (the competition ranking system was designed separately from first principles using the official JD and dataset)

## What is NOT here

The official competition ranking system lives in:

```
backend/competition/rank.py    ← entry point
backend/competition/
backend/intelligence/
backend/models/
backend/parsers/
backend/dataset_intelligence/loader.py
backend/reasoning/evidence_quality.py
backend/utils/skill_taxonomy.py
```
