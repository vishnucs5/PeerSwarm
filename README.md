# Multi-Agent Research Lab

An AI-powered, autonomous multi-agent research system featuring **CrewAI Flow orchestration**, peer-review quality evaluation loops, parallel agent visualizers, and a dual vector/graph database memory layer.

---

## 💡 The Market Gap We Fill

Standard AI search engines and simple RAG (Retrieval-Augmented Generation) systems operate on single-turn generation patterns. This results in **shallow, non-comprehensive research, unverified claims, and hallucinated sources**.

**Multi-Agent Research Lab** solves this by treating research as an iterative process:
* **Quality Gates (Hard & Soft Gates)**: Automatic self-evaluation scoring on five distinct quality dimensions.
* **Critique & Revision Loops**: If a report fails to meet the threshold, the flow is routed backwards to perform additional targeted research and analysis (up to 3 iterations).
* **Ground Truth & Citation Verification**: Parallel research agents cross-reference facts across Semantic Scholar, Tavily, and local vector stores to ensure absolute factual integrity.

---

## 🛠️ The Technology Stack

* **Orchestration**: `CrewAI Flow` (state management with decorator-based `@start`, `@listen`, and `@router` decorators).
* **LLM Engine**: `Groq API` (leveraging `llama-3.3-70b-versatile` for planning and evaluation, and `llama-3.1-8b-instant` for ultra-fast research).
* **Database & Memory**:
  * `Neo4j` (Entity-Relation Knowledge Graph mapping research findings).
  * `ChromaDB` (High-density vector database for semantic search).
  * `SQLite` (Job run history persistence).
  * `Redis` (Celery task queue broker and server-side cache).
* **Backend Server**: `FastAPI` (serving REST APIs and WebSockets), programmatically deployable to **Vercel Serverless (ASGI)**.
* **Frontend UI**: `Streamlit` (Swiss Modernism design system with tailored Atkinson Hyperlegible and Crimson Pro typography).

---

## 🤖 Multi-Agent Pipeline & Roles

The system uses a collaborative swarm of specialized AI agents:

```
                  ┌───────────────────────────────┐
                  │      Planner Agent (PI)       │
                  └───────────────┬───────────────┘
                                  ▼ (Structured Research Plan)
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Academic Res.  │      │    Web Res.     │      │   Local KB      │
│  (Researcher A) │      │  (Researcher B) │      │  (Researcher C) │
└────────┬────────┘      └────────┬────────┘      └────────┬────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼ (Factual Evidence & Claims)
                  ┌───────────────────────────────┐
                  │         Analyst Agent         │
                  └───────────────┬───────────────┘
                                  ▼ (Synthesis & Insight Clustering)
                  ┌───────────────────────────────┐
                  │         Writer Agent          │
                  └───────────────┬───────────────┘
                                  ▼ (Draft Report Generation)
                  ┌───────────────────────────────┐
                  │         Critic Agent          │
                  └───────────────┬───────────────┘
                                  ├──► [Passed] ──► Final Report Exporter
                                  └──► [Failed] ──► ↺ Loop back to Res./Analyst
```

1. **Planner Agent (Principal Investigator)**
   * *Role*: Decomposes complex user questions into 3-5 well-scoped sub-questions.
   * *Responsibility*: Assigns priorities, researcher roles, and search strategies (e.g. `academic_deep`, `industry_survey`, `gap_analysis`).

2. **Parallel Researcher Agents (A, B, and C)**
   * *Role*: Parallelized search engines.
   * *Responsibility*: Fetch evidence from Tavily, Serper, Semantic Scholar, and local vector stores, returning structured claims with citation URLs.

3. **Analyst Agent**
   * *Role*: Evaluator and Synthesizer.
   * *Responsibility*: Clusters findings, resolves contradictions, identifies evidence gaps, and builds the core synthesis.

4. **Writer Agent**
   * *Role*: Technical Copywriter.
   * *Responsibility*: Compiles the verified synthesis and citations into a premium, citation-rich markdown report.

5. **Critic Agent (Quality Control)**
   * *Role*: Peer Reviewer.
   * *Responsibility*: Scores the report on five dimensions (Factual Accuracy, Clarity, Completeness, Source Quality, Logical Coherence). Computes hard and soft quality gates to trigger revisions.

---

## ⚡ Main Features

* **Redesigned Modern Dashboard**: Interactive sidebar navigation, progress trackers, and detailed run tables.
* **Pipeline Progress Cards**: Live multi-column pipeline detailing which agent is currently active.
* **Dynamic ETAs**: Backend-calculated progress indicators.
* **Production Deployment**: 100% serverless API deployment available out of the box via Vercel.
