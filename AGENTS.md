# The 9-Agent Ecosystem

Self-Learning and Self-Healing RAG is powered by a highly specialized team of 9 autonomous agents. Instead of relying on one massive, monolithic LLM to do everything, the system divides the workload. 

By enforcing strict **Separation of Concerns**, the system ensures that the agent searching for evidence is structurally prohibited from evaluating the quality of that evidence. This prevents the AI from hallucinating or becoming overconfident in its own findings.

The agents are divided into two teams:
1. **The Hot Path (Real-time):** Agents 1, 2, 3, 4A, and 7. These work synchronously to answer your question in under 15 seconds.
2. **The Cold Path (Background):** Agents 4B, 5A, 5B, and 6. These work asynchronously (via Celery/Redis) to clean the database, learn from mistakes, and ingest new medical research.

---

## ⚡ The Hot Path (Real-Time Pipeline)

### 🔍 Agent 1: The Finder (Hybrid Retrieval)
**Role:** To scour the databases and find the most relevant biomedical evidence possible.
* **Input:** The raw user query.
* **Output:** The Top 5 highly relevant, verified data chunks.
* **Mechanics:** 
  1. It parses the user's intent.
  2. It runs a **Dense Search** using `S-PubMedBert-MS-MARCO` to find contextual meaning (e.g., matching "cancer" to "oncology").
  3. It runs a **Sparse Search** using `BM25` to find exact keyword matches (e.g., matching "pembrolizumab").
  4. It merges both searches using **Reciprocal Rank Fusion (RRF)**.
  5. It queries the **Neo4j Knowledge Graph** to find papers that *cite* or *contradict* the retrieved papers, expanding the search.
  6. It runs **Maximal Marginal Relevance (MMR)** to remove duplicates and ensure diversity.

### ⚖️ Agent 2: The Inspector (Quality Gate)
**Role:** To aggressively verify the evidence found by Agent 1. This is the most important agent in the system.
* **Input:** The Top 5 chunks from Agent 1.
* **Output:** A strict `PASS` or `FAIL`.
* **Mechanics:** Agent 2 runs a 5-step checklist. It **never** writes the answer. It only judges evidence.
  1. **Relevance:** Does the evidence directly answer the question?
  2. **Completeness:** Is the evidence missing crucial context?
  3. **Freshness:** Is the data too old? (Checks metadata dates).
  4. **Calibration:** It adjusts the system's "confidence score" based on past performance.
  5. **Contradiction:** It checks if the retrieved papers disagree with each other.
  *If Checks 1 or 2 fail, Agent 2 hard-blocks the system and triggers Agent 3 for repairs.*

### 🩺 Agent 3: The Detective (Root Cause Diagnosis)
**Role:** To figure out *why* Agent 1 failed to find good evidence.
* **Input:** The failed query and the rejected chunks.
* **Output:** A classified Error Type (Class A, B, or C).
* **Mechanics:** It runs automated diagnostics to classify the failure:
  * **Class A (Data Problem):** The information exists, but the embedding model failed to understand it, or it was split incorrectly during chunking.
  * **Class B (Knowledge Gap):** The system literally does not have the answer in its database.
  * **Class C (Strategy Problem):** The database has the answer, but Agent 1 used the wrong search keywords.
  *Class A and B errors are sent to the background (Agent 4B). Class C errors are sent to Agent 4A for immediate repair.*

### 🎯 Agent 4A: The Formulator (Immediate Repair)
**Role:** To fix Class C errors in real-time before the user even notices a failure.
* **Input:** The root cause diagnosis from Agent 3.
* **Output:** New, highly targeted sub-queries.
* **Mechanics:**
  1. It performs a **Gap Analysis** to see exactly what information is missing.
  2. It generates new sub-queries to target the missing data.
  3. **Live Fetch:** If it determines the data is missing because it's too new (Knowledge Drift), it will ping the live PubMed API to fetch papers from the last 30 days.
  4. It sends the new queries back to Agent 1, merges the new findings, and submits them back to Agent 2 for re-evaluation.

### ✍️ Agent 7: The Writer (Generator)
**Role:** To write the final, human-readable answer.
* **Input:** Evidence that has explicitly passed Agent 2's Quality Gate.
* **Output:** The final response sent to the React UI.
* **Mechanics:** 
  1. It looks at the query and decides the best format (e.g., if you ask for side effects, it writes a list; if you ask for a comparison, it draws a Markdown table).
  2. It generates the response.
  3. It explicitly embeds inline citations pointing to the exact PubMed chunks used.
  4. If the Repair Cycle failed and the system still doesn't have the full answer, Agent 7 is strictly instructed to be honest and tell the user exactly what is missing.

---

## 🌙 The Cold Path (Asynchronous Maintenance)

### 🔧 Agent 4B: The Mechanic (Corpus Repair)
**Role:** To fix structural database issues in the background without slowing down the user.
* **Input:** Class A and B errors from Agent 3.
* **Output:** Database repairs and queueing new papers for ingestion.
* **Mechanics:** Runs via Celery tasks. If the system discovers a massive knowledge gap (e.g., users keep asking about a new disease the database doesn't know), Agent 4B queues a mass-download of relevant PubMed literature to permanently fix the gap for future users.

### ✅ Agent 5A: The Verifier (Literature Gate)
**Role:** To prevent junk science from entering the system.
* **Input:** Raw PDFs and abstracts from PubMed or arXiv.
* **Output:** Approval or Rejection of the paper.
* **Mechanics:** Before any new paper is ingested, Agent 5A checks:
  1. **Domain:** Is it strictly biomedical?
  2. **Quality:** Is it peer-reviewed or an RCT (Randomized Controlled Trial)?
  3. **Impact:** Does it have a high citation velocity?
  *If a paper fails, it is permanently discarded.*

### 📥 Agent 5B: The Ingester (Data Processing)
**Role:** To properly chunk and embed approved papers.
* **Input:** Papers approved by Agent 5A.
* **Output:** Searchable Vectors and Graph nodes.
* **Mechanics:** 
  1. It breaks the paper down into a hierarchy: `Document -> Section -> Chunk -> Fact Claim`.
  2. It generates 768-dimensional vectors using `S-PubMedBert`.
  3. It places the chunks in a "Staging Database" where it runs 3 synthetic test queries. 
  4. Only if the chunks are successfully retrievable does it promote them to the live Qdrant Production database.

### 🧠 Agent 6: The Brain (Learning Engine)
**Role:** To monitor the entire system and make it smarter over time.
* **Input:** Every query result, pass/fail rate, and user feedback (thumbs up/down).
* **Output:** System optimizations.
* **Mechanics:** Runs nightly via Celery. 
  1. It tracks the system's "Calibration Curve" (e.g., if Agent 2 says it is 90% confident, but users vote it down, Agent 6 dynamically lowers the system's future confidence multipliers).
  2. It tracks Topic Velocity. If a topic (like a new virus) is changing rapidly, Agent 6 lowers the Redis Cache TTL (Time-To-Live) for that topic so the system is forced to re-fetch fresh data more often.
  3. It provides an insights dashboard for system admins.
