from google import genai
from dataclasses import dataclass, field
from config import get_config
from utils.logger import get_logger
from utils.llm_utils import get_gemini_key
from agents.agent1_retrieval import QueryClassifier, MetadataPreFilter
from utils.thought_logger import ThoughtLogger

from agents.models import (
    SubQuery, LiveFetchResult, FormulationResult,
    FilterConfig
)

class Agent4AFormulator:
    """
    Agent 4A: Gap Analysis and Retrieval Formulator.
    Triggered when Agent 3 identifies a Class C (Query Problem) or Class B (Knowledge Drift).
    Breaks down the query and formulates targeted sub-queries or executes live PubMed fetches.
    """
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.classifier = QueryClassifier()
        self.pre_filter = MetadataPreFilter()

    def _handle_knowledge_drift(self, query: str, classification, retrieval_results: list) -> LiveFetchResult:
        self.logger.info("Executing live PubMed fetch for knowledge_drift...")
        try:
            import requests
            import xmltodict
            
            # Step 1 - Call PubMed E-utilities esearch
            esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": 5,
                "retmode": "json",
                "sort": "relevance",
                "datetype": "pdat",
                "mindate": 2020,
                "maxdate": 2024
            }
            if self.config.ncbi_api_key:
                params["api_key"] = self.config.ncbi_api_key
                
            r = requests.get(esearch_url, params=params, timeout=10.0)
            r.raise_for_status()
            search_data = r.json()
            
            pmids = search_data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                self.logger.info("Live fetch for knowledge_drift: 0 papers found")
                return LiveFetchResult(success=False, query_used=query)
                
            # Step 2 - Fetch abstracts for found PMIDs
            efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "rettype": "abstract",
                "retmode": "xml"
            }
            if self.config.ncbi_api_key:
                fetch_params["api_key"] = self.config.ncbi_api_key
                
            r_fetch = requests.get(efetch_url, params=fetch_params, timeout=10.0)
            r_fetch.raise_for_status()
            
            xml_data = xmltodict.parse(r_fetch.text)
            
            # Navigate XML. Handle both single article (dict) or multiple (list)
            article_set = xml_data.get("PubmedArticleSet", {}) or {}
            articles = article_set.get("PubmedArticle", [])
            if isinstance(articles, dict):
                articles = [articles]
                
            valid_chunks = []
            for article in articles:
                try:
                    medline = article.get("MedlineCitation", {}) or {}
                    pmid_obj = medline.get("PMID", "")
                    if isinstance(pmid_obj, dict):
                        pmid = pmid_obj.get("#text", "")
                    else:
                        pmid = str(pmid_obj)
                        
                    if not pmid:
                        continue
                        
                    article_data = medline.get("Article", {}) or {}
                    title_obj = article_data.get("ArticleTitle", "")
                    if isinstance(title_obj, dict):
                        title = title_obj.get("#text", str(title_obj))
                    elif isinstance(title_obj, list):
                        title = " ".join([t.get("#text", str(t)) if isinstance(t, dict) else str(t) for t in title_obj])
                    else:
                        title = str(title_obj)
                        
                    abstract_data = article_data.get("Abstract", {}) or {}
                    abstract_text = ""
                    abstract_text_element = abstract_data.get("AbstractText", "")
                    if isinstance(abstract_text_element, list):
                        abstract_text = " ".join([t.get("#text", str(t)) if isinstance(t, dict) else str(t) for t in abstract_text_element])
                    elif isinstance(abstract_text_element, dict):
                        abstract_text = abstract_text_element.get("#text", str(abstract_text_element))
                    else:
                        abstract_text = str(abstract_text_element)
                        
                    if len(abstract_text) <= 100:
                        continue
                        
                    pub_date = article_data.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {}) or {}
                    year = 2022  # default fallback
                    year_val = pub_date.get("Year", "")
                    if year_val:
                        try:
                            year = int(year_val)
                        except ValueError:
                            pass
                            
                    journal_name = article_data.get("Journal", {}).get("Title", "")
                    
                    # Detect topic cluster from query
                    q_lower = query.lower()
                    if any(kw in q_lower for kw in ["pd-1", "pd-l1", "pembrolizumab", "nivolumab", "immunotherapy", "checkpoint", "car-t"]):
                        topic_cluster = "immunotherapy"
                    elif any(kw in q_lower for kw in ["drug interaction", "cytochrome", "p450", "pharmacokinetics", "adverse"]):
                        topic_cluster = "drug_interactions"
                    elif any(kw in q_lower for kw in ["gene", "genome", "crispr", "snp", "sequencing", "genomics"]):
                        topic_cluster = "genomics"
                    else:
                        topic_cluster = "immunotherapy"
                        
                    valid_chunks.append({
                        "chunk_id": f"live_{pmid}",
                        "paper_id": pmid,
                        "text": abstract_text,
                        "title": title,
                        "year": year,
                        "journal": journal_name,
                        "score": 0.75,
                        "level": "semantic",
                        "section_type": "abstract",
                        "topic_cluster": topic_cluster,
                        "freshness_score": 1.0,
                        "contradiction_flag": False,
                        "evidence_level": "other",
                        "keyword_matches": 0
                    })
                except Exception as ex:
                    self.logger.warning(f"Failed to parse an article abstract: {ex}")
                    continue
                    
            if valid_chunks:
                # Step 5 - Queue background ingestion
                try:
                    from workers.repair_tasks import ingest_live_fetch_papers
                    paper_ids = [c['paper_id'] for c in valid_chunks]
                    ingest_live_fetch_papers.delay(paper_ids, query)
                    self.logger.info(
                        f"Queued {len(paper_ids)} papers for permanent ingestion"
                    )
                except Exception as e:
                    self.logger.warning(f"Could not queue ingestion task: {e}")
                
            self.logger.info(f"Live fetch for knowledge_drift: {len(valid_chunks)} papers found")
            return LiveFetchResult(
                source="pubmed_live",
                papers_fetched=len(pmids),
                chunks_returned=valid_chunks,
                query_used=query,
                success=len(valid_chunks) > 0
            )
            
        except Exception as e:
            self.logger.error(f"Live fetch crashed: {e}")
            return LiveFetchResult(success=False, query_used=query)

    def formulate(self, query: str, classification, retrieval_results: list, agent2_result, diagnosis) -> FormulationResult:
        self.logger.info("Starting Agent 4A Formulation...")
        
        try:
            tl = ThoughtLogger(session_id='', agent='agent4a')
            
            # Check for knowledge_drift at start
            if diagnosis and getattr(diagnosis, "root_cause", "") == "knowledge_drift":
                self.logger.info("knowledge_drift detected — triggering live fetch")
                live_result = self._handle_knowledge_drift(query, classification, retrieval_results)
                res = FormulationResult(
                    original_query=query,
                    sub_queries=[],
                    gaps_identified=["knowledge_drift — corpus stale"],
                    strategy_explanation="Live fetch from PubMed API",
                    live_fetch_result=live_result,
                    used_live_fetch=True
                )
                try:
                    tl.trace(
                        step='formulate',
                        obs="Diagnosis is knowledge_drift. Local corpus is stale.",
                        thk="External live fetch is required to gather fresh evidence.",
                        act="Trigger PubMed E-utilities live fetch. Queue background ingestion.",
                        out=f"Live fetch returned {live_result.papers_fetched} papers. "
                            f"{'Success' if live_result.success else 'Failed'}",
                        confidence=0.9
                    )
                    res.thought_traces = tl.get_traces()
                except Exception: pass
                return res
                
            # Step 1: Gap Analysis
            # Try to get gaps from Agent 2 completeness check first
            gaps = getattr(agent2_result, 'coverage_gaps', [])
            
            # If no formal gaps, compare query entities to retrieved text
            if not gaps:
                topics = set(t.lower() for t in getattr(classification, 'main_topics', []))
                entities = set(e.lower() for e in getattr(classification, 'entities', []))
                query_terms = list(topics.union(entities))
                
                retrieved_text = " ".join((r.text if hasattr(r, 'text') else r.get('text', '')).lower() for r in retrieval_results)
                
                missing_terms = [t for t in query_terms if t not in retrieved_text]
                if missing_terms:
                    gaps.append(f"Missing information regarding: {', '.join(missing_terms)}")
                    
            # Absolute fallback gap if everything overlaps but relevance still failed
            if not gaps:
                gaps.append("General semantic misalignment or under-representation of query intent")
                
            # Step 2: Coverage Mapping
            # Decide if these gaps should be searched internally or externally
            internal_gaps = []
            if diagnosis and diagnosis.root_cause == "coverage_gap":
                # Known to be external/missing from corpus entirely
                pass
            elif diagnosis and diagnosis.root_cause in ["query_formulation", "query_too_narrow", "unknown_query_issue"]:
                # Known or assumed to be internal
                internal_gaps = gaps
            else:
                # Default to internal attempt
                internal_gaps = gaps
                
            # Step 3: Sub-Query Formulation via LLM
            sub_queries = []
            if internal_gaps:
                for gap in internal_gaps:
                    try:
                        client = genai.Client(api_key=get_gemini_key())
                        prompt = (
                            f"I need to find biomedical information about: {gap}\n"
                            f"In the context of: {query}\n\n"
                            f"Write one precise PubMed-style search query that would "
                            f"find papers specifically about this gap.\n"
                            f"Use medical terminology. Be specific.\n"
                            f"Reply with ONLY the search query string."
                        )
                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=prompt
                        )
                        sub_text = response.text.strip().strip('"\'')
                        
                        # Re-run Agent 1's frontend on the new sub-query
                        sub_class = self.classifier.classify(sub_text)
                        sub_filter = self.pre_filter.build_filter(sub_class)
                        
                        sub_queries.append(SubQuery(
                            query_text=sub_text,
                            strategy=sub_class.query_type,
                            filter_config=sub_filter,
                            target_gap=gap
                        ))
                    except Exception as e:
                        self.logger.warning(f"Failed to formulate specific sub-query for gap '{gap}': {e}")
                        
            # Step 4: Fallback formulation (if no internal gaps, or LLM failed completely)
            if not sub_queries:
                self.logger.info("Using fallback query formulation (broadening strategy)")
                
                broad_query = query
                # Broaden by dropping the most restrictive terms
                entities = getattr(classification, 'entities', [])
                topics = getattr(classification, 'main_topics', [])
                
                if len(entities) > 1:
                    # Drop the last entity to make it broader
                    broad_query = " ".join(entities[:-1] + topics)
                elif len(topics) > 1:
                    broad_query = " ".join(topics)
                    
                sub_class = self.classifier.classify(broad_query)
                sub_filter = self.pre_filter.build_filter(sub_class)
                
                sub_queries.append(SubQuery(
                    query_text=broad_query,
                    strategy=sub_class.query_type,
                    filter_config=sub_filter,
                    target_gap="General broadening of the original query"
                ))
                
            res = FormulationResult(
                original_query=query,
                sub_queries=sub_queries,
                gaps_identified=gaps,
                strategy_explanation=f"Formulated {len(sub_queries)} targeted sub-queries to resolve diagnosis: {diagnosis.root_cause if diagnosis else 'unknown'}"
            )
            try:
                tl.trace(
                    step='formulate',
                    obs=f"Gap analysis identified {len(gaps)} gaps. "
                        f"Diagnosis: {diagnosis.root_cause if diagnosis else 'unknown'}.",
                    thk="Internal corpus search is viable. Breaking down gaps into precise sub-queries.",
                    act=f"Formulate {len(sub_queries)} sub-queries via Gemini.",
                    out=f"Sub-queries generated: {[q.query_text for q in sub_queries]}",
                    confidence=0.85
                )
                res.thought_traces = tl.get_traces()
            except Exception: pass
            return res
            
        except Exception as e:
            self.logger.error(f"Agent 4A encountered an unexpected error: {e}")
            # Never Crash - return the safest fallback
            safe_class = self.classifier.classify(query)
            safe_filter = self.pre_filter.build_filter(safe_class)
            return FormulationResult(
                original_query=query,
                sub_queries=[SubQuery(query, safe_class.query_type, safe_filter, "Absolute fallback due to system error")],
                gaps_identified=["System failure during gap analysis"],
                strategy_explanation="Fallback formulation"
            )
