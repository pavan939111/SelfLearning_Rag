import time
from datetime import datetime, timedelta, timezone
from utils.logger import get_logger
from ingestion.fetcher import PubMedFetcher
from agents.agent5a_verifier import Agent5AVerifier
from agents.live_fetch_ingester import LiveFetchIngester
from agents.agent6_learning import Agent6Learning

class StreamMonitor:
    MONITOR_QUERIES = {
        "immunotherapy": [
            "pembrolizumab nivolumab checkpoint inhibitor 2024",
            "CAR-T cell therapy clinical trial 2024",
            "PD-L1 immunotherapy NSCLC 2024",
        ],
        "drug_interactions": [
            "cytochrome P450 drug interaction 2024",
            "adverse drug reaction polypharmacy 2024",
            "pharmacokinetics drug metabolism 2024",
        ],
        "genomics": [
            "CRISPR gene editing clinical 2024",
            "genome sequencing cancer 2024",
            "SNP biomarker disease 2024",
        ]
    }

    def __init__(self):
        self.fetcher = PubMedFetcher()
        self.verifier = Agent5AVerifier()
        self.ingester = LiveFetchIngester()
        self.agent6 = Agent6Learning()
        self.logger = get_logger(__name__)

    def run_daily_sweep(self) -> dict:
        self.logger.info("Starting daily stream monitor sweep...")
        results = {
            'papers_found': 0,
            'papers_verified': 0,
            'papers_ingested': 0,
            'papers_rejected': 0,
            'by_cluster': {}
        }
        
        thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y/%m/%d")
        today = datetime.now(timezone.utc).strftime("%Y/%m/%d")

        for cluster, queries in self.MONITOR_QUERIES.items():
            results['by_cluster'][cluster] = 0
            for query in queries:
                try:
                    # Append date filters directly or use fetcher capability if it supports mindate/maxdate
                    search_query = f"({query}) AND (\"{thirty_days_ago}\"[Date - Publication] : \"{today}\"[Date - Publication])"
                    # Semantic Scholar API equivalent will just use the query, but we'll use PubMed via fetcher
                    pmids = self.fetcher.search_pmids(search_query, max_results=5, topic_cluster=cluster)
                    
                    for pmid in pmids:
                        results['papers_found'] += 1
                        raw_data = self.fetcher.fetch_abstracts_batch([pmid])
                        if not raw_data:
                            continue
                            
                        paper = self.fetcher.parse_article(raw_data[0], cluster)
                        if not paper:
                            continue
                            
                        verification = self.verifier.verify(paper)
                        if verification.passed:
                            results['papers_verified'] += 1
                            
                            if self.ingester.check_already_ingested(paper.paper_id):
                                continue
                                
                            rule_matched = verification.ingestion_instructions.get('rule_matched', '')
                            priority = 'high' if 'HighPriority' in rule_matched else 'medium'
                            
                            if priority == 'high':
                                self.ingester.ingest_single(paper)
                                results['papers_ingested'] += 1
                                results['by_cluster'][cluster] += 1
                            else:
                                # Queue for batch ingestion (placeholder for Celery)
                                self.logger.info(f"Queued paper {paper.paper_id} for batch ingestion.")
                        else:
                            results['papers_rejected'] += 1
                            self.logger.info(f"Rejected paper {paper.paper_id}: {verification.rejection_reason}")
                            
                    time.sleep(1.1)
                except Exception as e:
                    self.logger.warning(f"Error during sweep for query '{query}': {e}")
                    
        # After sweep: Notify Agent 6
        try:
            # Need to create observe_ingestion_event if it doesn't exist yet, wrap in try/except
            if hasattr(self.agent6, 'observe_ingestion_event'):
                self.agent6.observe_ingestion_event(
                    papers_ingested=results['papers_ingested'],
                    by_cluster=results['by_cluster']
                )
        except Exception as e:
            self.logger.warning(f"Failed to notify Agent 6: {e}")
            
        self.logger.info(f"Daily sweep complete: {results}")
        return results

    def run_gap_targeted_sweep(self) -> dict:
        self.logger.info("Starting gap-targeted sweep...")
        results = {
            'papers_found': 0,
            'papers_verified': 0,
            'papers_ingested': 0,
            'papers_rejected': 0,
            'by_cluster': {}
        }
        
        try:
            gaps = self.agent6.get_coverage_gaps(min_query_count=3)
            # Sort by query_count desc
            gaps = sorted(gaps, key=lambda g: g.get('query_count', 0), reverse=True)
            
            for gap in gaps:
                topic = gap.get('topic')
                if not topic: continue
                
                query = f"{topic} clinical evidence 2024"
                cluster = gap.get('topic_cluster', 'immunotherapy')
                
                try:
                    pmids = self.fetcher.search_pmids(query, max_results=10, topic_cluster=cluster)
                    found_relevant = 0
                    
                    for pmid in pmids:
                        results['papers_found'] += 1
                        raw_data = self.fetcher.fetch_abstracts_batch([pmid])
                        if not raw_data: continue
                        
                        paper = self.fetcher.parse_article(raw_data[0], cluster)
                        if not paper: continue
                        
                        verification = self.verifier.verify(paper)
                        if verification.passed:
                            results['papers_verified'] += 1
                            if not self.ingester.check_already_ingested(paper.paper_id):
                                self.ingester.ingest_single(paper)
                                results['papers_ingested'] += 1
                                results['by_cluster'][cluster] = results['by_cluster'].get(cluster, 0) + 1
                                found_relevant += 1
                        else:
                            results['papers_rejected'] += 1
                            
                    self.logger.info(f"Gap-targeted sweep for {topic}: found {found_relevant} relevant papers")
                    time.sleep(1.1)
                except Exception as e:
                    self.logger.warning(f"Error during gap sweep for topic '{topic}': {e}")
                    
        except Exception as e:
            self.logger.warning(f"Error in run_gap_targeted_sweep: {e}")
            
        self.logger.info(f"Gap sweep complete: {results}")
        return results
