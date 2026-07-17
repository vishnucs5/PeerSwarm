# PeerSwarm

An AI-powered, autonomous multi-agent research system featuring **CrewAI Flow orchestration**, peer-review quality evaluation loops, parallel agent visualizers, and a dual vector/graph database memory layer.

---

## 💡 The Market Gap We Fill

Standard AI search engines and simple RAG (Retrieval-Augmented Generation) systems operate on single-turn generation patterns. This results in **shallow, non-comprehensive research, unverified claims, and hallucinated sources**.

**PeerSwarm** solves this by treating research as an iterative process:
* **Quality Gates (Hard & Soft Gates)**: Automatic self-evaluation scoring on five distinct quality dimensions.
* **Critique & Revision Loops**: If a report fails to meet the threshold, the flow is routed backwards to perform additional targeted research and analysis (up to 5 iterations).
* **Ground Truth & Citation Verification**: Parallel research agents cross-reference facts across Semantic Scholar, Tavily, and local vector stores to ensure absolute factual integrity.

---

## 🚀 Key Features

### Core Architecture
* **7 Specialized AI Agents**: Orchestrated via CrewAI Flow including Planner (PI), 3 parallel Researchers (Academic, Web, Knowledge Base), Analyst, Writer, and Critic.
* **Iterative Quality Loops**: Automatic self-evaluation on 5 dimensions (Accuracy, Completeness, Clarity, Relevance, Depth) with hard gates (< 6/10) and configurable thresholds; reports below grade trigger automatic revision cycles (up to 5 iterations).
* **Structured Research Pipeline**: Question → Plan → Parallel Research → Synthesis → Draft → Critique → Revision → Final Report.

### Backend & Storage
* **Groq-Powered LLM Inference**: Utilizing `llama-3.3-70b-versatile` for planning/evaluation and `llama-3.1-8b-instant` for fast parallel research.
* **Hybrid Memory Layer**: ChromaDB (vector embeddings for semantic search) + Neo4j (knowledge graph for entity-relation mapping) + SQLite/PostgreSQL for run history.
* **Supabase PostgreSQL**: Persistent job/result storage (no data loss on server restarts).
* **Vercel-Deployable FastAPI Backend**: Full ASGI serverless support for instant cloud deployment.

### Frontend
* **Swiss Modernism 2.0 Design System**: Streamlit dashboard with Crimson Pro headings, Atkinson Hyperlegible body typography, and a tailored 8px spacing grid.
* **5-Page UI Dashboard**:
  * *New Research*: Submit new research questions with specific parameters.
  * *Live Job Status*: Real-time pipeline step visualization and parallel agent execution cards.
  * *Results*: View executive summary, key takeaways, expandable content sections, and download as Markdown/JSON.
  * *History*: Filterable and searchable run history logs.
  * *System Health*: Complete connection checkers for downstream services.
* **Supabase Direct-Read Fallback**: Streamlit frontend can directly read run history from Supabase even if the API server is offline.

### DevOps
* **100% Serverless-Ready**: Deploy the API backend to Vercel in one simple command.
* **Docker Compose**: Containerized environment for local development running all dependencies (Neo4j, ChromaDB, Redis).
* **Observability**: Prometheus metrics, structured JSON logging, and pre-commit verification hooks.

### CLI (Typer CLI Interface)
* Includes commands for: `run`, `plan`, `evaluate`, `list-reports`, `stats`, and `version`.

---

## 🤖 Multi-Agent Pipeline & Roles

```
                                 [ USER REQUEST ]
                        (Streamlit UI / Typer CLI / REST API)
                                         │
                                         ▼
                      ┌─────────────────────────────────────┐
                      │        Planner Agent (PI)           │
                      │  (Decomposes into Sub-Questions)    │
                      └──────────────────┬──────────────────┘
                                         │ (Structured Research Plan)
         ┌───────────────────────────────┼───────────────────────────────┐
         ▼ (Academic Deep)               ▼ (Industry Survey)             ▼ (Local KB Search)
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│     Academic Res.       │     │        Web Res.         │     │        Local KB         │
│     (Researcher A)      │     │     (Researcher B)      │     │     (Researcher C)      │
└────────┬────────────────┘     └────────┬────────────────┘     └────────┬────────────────┘
         │ (Semantic Scholar API)        │ (Tavily/Serper Search)        │ (Local ChromaDB Read)
         ▼                               ▼                               ▼
         └───────────────────────────────┼───────────────────────────────┘
                                         │ (Raw Factual Claims & Citations)
                                         ▼
                      ┌─────────────────────────────────────┐
                      │            Analyst Agent            │◄───────────────────────┐
                      │  (Clusters Claims & Resolves Gaps)   ├────────────────┐       │
                      └──────────────────┬──────────────────┘                │       │
                                         │                                   │       │
                                         ├─────────────────────────────┐     │       │
                                         │ (Entity-Relation Extraction)│     │       │
                                         ▼                             ▼     │       │
                              ┌────────────────────┐        ┌────────────────┐       │
                              │    Neo4j Graph     │        │ Supabase Run   │       │
                              │  (Knowledge Base)  │        │ (State Sync)   │       │
                              └────────────────────┘        └────────────────┘       │
                                         │ (Synthesized Narrative)           │       │
                                         ▼                                   │       │
                      ┌─────────────────────────────────────┐                │       │
                      │            Writer Agent             │                │       │
                      │   (Drafts Markdown with Citations)  │                │       │
                      └──────────────────┬──────────────────┘                │       │
                                         │ (Draft Research Report)           │       │
                                         ▼                                   │       │
                      ┌─────────────────────────────────────┐                │       │
                      │            Critic Agent             │                │       │
                      │   (Evaluates against Quality Gates) │                │       │
                      └──────────────────┬──────────────────┘                │       │
                                         │                                   │       │
                     [Has Quality Passed?]                                   │       │
                       ├───► [Passed] ───┼───────────────────────────────────┼───────┘
                       │                 │ (Write Report Run Logs)           │
                       │                 ▼                                   ▼
                       │       ┌────────────────────┐             ┌────────────────────┐
                       │       │ SQLite Run History │             │ Exporter Component │
                       │       │   (Local DB Logs)  │             │ (Markdown / JSON)  │
                       │       └────────────────────┘             └────────────────────┘
                       │                                                     │
                       │                                                     ▼
                       │                                              [ FINAL REPORT ]
                       │
                       └───► [Failed (<6/10 Hard Gate / Soft Gate)]
                                         │
                                         ▼
                             (Triggers Revision Loop)
                      ┌─────────────────────────────────────┐
                      │           Revision Task             │
                      │ (Extracts Critique Recommendations) ├────────────────────────┘
                      └─────────────────────────────────────┘
                                   (Max 5 Iterations)
```
