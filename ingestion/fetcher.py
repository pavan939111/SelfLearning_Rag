import requests
import time
import datetime
import xmltodict
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from tenacity import retry, stop_after_attempt, wait_fixed
from config import get_config
from utils.logger import get_logger

# Initialize configuration
config = get_config()

@dataclass
class PaperRecord:
    paper_id: str          # PubMed PMID
    title: str
    authors: list[str]
    journal: str
    year: int
    abstract: str
    doi: str               # empty string if not available
    topic_cluster: str     # immunotherapy / drug_interactions / genomics
    evidence_level: str    # review / rct / cohort / case_report / other
    ingestion_date: str    # ISO format 2024-01-15
    freshness_score: float # always 1.0 for new papers
    contradiction_flag: bool  # always False for new papers
    has_full_text: bool    # False for now - abstract only

    def to_dict(self) -> dict:
        """Returns all fields as flat dictionary."""
        data = asdict(self)
        data["authors"] = ", ".join(self.authors)
        return data

TOPIC_QUERIES = {
    "immunotherapy": (
        "immunotherapy[MeSH] OR checkpoint inhibitor[tiab] OR "
        "PD-1[tiab] OR PD-L1[tiab] OR pembrolizumab[tiab] OR "
        "nivolumab[tiab] OR CAR-T[tiab]"
    ),
    "drug_interactions": (
        "drug interaction[MeSH] OR drug-drug interaction[tiab] OR "
        "adverse drug reaction[tiab] OR pharmacokinetics[MeSH] OR "
        "cytochrome P450[tiab] OR polypharmacy[tiab]"
    ),
    "genomics": (
        "genomics[MeSH] OR genome sequencing[tiab] OR "
        "CRISPR[tiab] OR gene expression[MeSH] OR "
        "single nucleotide polymorphism[tiab] OR SNP[tiab] OR "
        "epigenetics[MeSH]"
    )
}

class PubMedFetcher:
    def __init__(self):
        self.api_key = config.ncbi_api_key
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.delay = 0.34 if not self.api_key else 0.1
        self.logger = get_logger(__name__)
        self.logger.info(f"PubMedFetcher initialized (API Key: {'Yes' if self.api_key else 'No'})")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def search_pmids(self, query: str, max_results: int, topic_cluster: str) -> list[str]:
        """Calls esearch.fcgi endpoint to retrieve PMIDs."""
        url = f"{self.base_url}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
            "datetype": "pdat",
            "mindate": 2015,
            "maxdate": 2024
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            self.logger.info(f"Found {len(pmids)} PMIDs for {topic_cluster}")
            
            time.sleep(self.delay)
            return pmids
        except Exception as e:
            self.logger.error(f"Error searching PMIDs for {topic_cluster}: {e}")
            return []

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def fetch_abstracts_batch(self, pmids: list[str]) -> list[dict]:
        """Calls efetch.fcgi to retrieve XML data for a batch of PMIDs."""
        if not pmids:
            return []
            
        url = f"{self.base_url}efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml"
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # Parse XML
            data = xmltodict.parse(response.text)
            if not data or "PubmedArticleSet" not in data:
                return []
                
            articles = data["PubmedArticleSet"].get("PubmedArticle", [])
            if isinstance(articles, dict):
                articles = [articles]
                
            time.sleep(self.delay)
            return articles
        except Exception as e:
            self.logger.error(f"Error fetching abstracts batch: {e}")
            return []

    def parse_article(self, raw: dict, topic_cluster: str) -> PaperRecord | None:
        """Parses raw PubMed article dict into a PaperRecord."""
        paper_id = "Unknown"
        try:
            medline = raw.get("MedlineCitation", {})
            article = medline.get("Article", {})
            
            # paper_id
            pmid_data = medline.get("PMID", {})
            if isinstance(pmid_data, dict):
                paper_id = pmid_data.get("#text", "Unknown")
            else:
                paper_id = str(pmid_data)

            # title
            title_data = article.get("ArticleTitle", "No Title")
            if isinstance(title_data, dict):
                title = title_data.get("#text", str(title_data))
            else:
                title = str(title_data)

            # authors
            authors = []
            try:
                author_list = article.get("AuthorList", {}).get("Author", [])
                if isinstance(author_list, dict):
                    author_list = [author_list]
                
                for auth in author_list[:10]:
                    if "CollectiveName" in auth:
                        authors.append(str(auth["CollectiveName"]))
                    else:
                        lname = auth.get("LastName", "")
                        fname = auth.get("ForeName", "")
                        if fname:
                            authors.append(f"{lname} {fname}".strip())
                        else:
                            authors.append(str(lname))
                
                if len(author_list) > 10:
                    authors.append("et al.")
            except:
                authors = ["Unknown"]
            
            if not authors:
                authors = ["Unknown"]

            # journal
            journal = "Unknown Journal"
            try:
                journal_data = article.get("Journal", {})
                journal = journal_data.get("Title") or journal_data.get("ISOAbbreviation") or "Unknown Journal"
            except:
                pass

            # year
            year = 2020
            try:
                pub_date = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
                year_str = pub_date.get("Year") or pub_date.get("MedlineDate", "")[:4] or medline.get("DateCompleted", {}).get("Year")
                if year_str:
                    year = int(year_str)
            except:
                year = 2020

            # abstract
            abstract = None
            try:
                abstract_data = article.get("Abstract", {}).get("AbstractText")
                if isinstance(abstract_data, str):
                    abstract = abstract_data
                elif isinstance(abstract_data, list):
                    abstract = " ".join([str(item.get("#text", item)) if isinstance(item, dict) else str(item) for item in abstract_data])
                elif isinstance(abstract_data, dict):
                    abstract = abstract_data.get("#text")
            except:
                abstract = None
            
            if not abstract:
                return None

            # doi
            doi = ""
            try:
                elocations = article.get("ELocationID", [])
                if isinstance(elocations, dict):
                    elocations = [elocations]
                for loc in elocations:
                    if isinstance(loc, dict) and loc.get("@EIdType") == "doi":
                        doi = loc.get("#text", str(loc))
                        break
                    elif isinstance(loc, str) and "/" in loc:
                        doi = loc
            except:
                doi = ""

            # evidence_level
            title_lower = title.lower()
            abstract_lower = abstract.lower()
            if any(word in title_lower for word in ["systematic review", "meta-analysis", "cochrane"]):
                evidence_level = "review"
            elif any(word in title_lower or word in abstract_lower for word in ["randomized", "randomised", "rct", "clinical trial"]):
                evidence_level = "rct"
            elif any(word in abstract_lower for word in ["cohort", "observational", "prospective", "retrospective"]):
                evidence_level = "cohort"
            elif any(word in abstract_lower for word in ["case report", "case study", "case series"]):
                evidence_level = "case_report"
            else:
                evidence_level = "other"

            record = PaperRecord(
                paper_id=paper_id,
                title=title,
                authors=authors,
                journal=journal,
                year=year,
                abstract=abstract,
                doi=doi,
                topic_cluster=topic_cluster,
                evidence_level=evidence_level,
                ingestion_date=datetime.date.today().isoformat(),
                freshness_score=1.0,
                contradiction_flag=False,
                has_full_text=False
            )
            
            self.logger.debug(f"Parsed: {paper_id} | {year} | {topic_cluster}")
            return record

        except Exception as e:
            self.logger.error(f"Error parsing paper {paper_id}: {e}")
            return None

    def fetch_cluster(self, topic_cluster: str, max_papers: int = 600) -> list[PaperRecord]:
        """Retrieves and parses papers for a specific topic cluster."""
        query = TOPIC_QUERIES.get(topic_cluster)
        if not query:
            self.logger.error(f"Unknown cluster: {topic_cluster}")
            return []

        pmids = self.search_pmids(query, max_results=max_papers, topic_cluster=topic_cluster)
        if not pmids:
            return []

        papers = []
        seen_ids = set()
        
        for i in range(0, len(pmids), 20):
            batch = pmids[i:i+20]
            raw_articles = self.fetch_abstracts_batch(batch)
            for raw in raw_articles:
                paper = self.parse_article(raw, topic_cluster)
                if paper and paper.paper_id not in seen_ids:
                    papers.append(paper)
                    seen_ids.add(paper.paper_id)
            
            if len(papers) % 100 == 0 and len(papers) > 0:
                self.logger.info(f"{topic_cluster}: {len(papers)} papers so far")
        
        self.logger.info(f"Finished {topic_cluster}: {len(papers)} papers total")
        return papers

    def fetch_all_clusters(self, papers_per_cluster: int = 600) -> list[PaperRecord]:
        """Fetches papers across all defined clusters and deduplicates them."""
        all_papers = []
        seen_ids = set()
        
        for cluster in ["immunotherapy", "drug_interactions", "genomics"]:
            self.logger.info(f"Starting cluster: {cluster}")
            cluster_papers = self.fetch_cluster(cluster, papers_per_cluster)
            
            for p in cluster_papers:
                if p.paper_id not in seen_ids:
                    all_papers.append(p)
                    seen_ids.add(p.paper_id)
                    
        self.logger.info(f"Total papers fetched: {len(all_papers)}")
        return all_papers

def save_papers(papers: list[PaperRecord], filepath: str) -> None:
    """Saves a list of PaperRecord objects to a .jsonl file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            for p in papers:
                f.write(json.dumps(p.to_dict()) + "\n")
        logger = get_logger(__name__)
        logger.info(f"Saved {len(papers)} papers to {filepath}")
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to save papers: {e}")

def load_papers(filepath: str) -> list[PaperRecord]:
    """Loads papers from a .jsonl file and reconstructs PaperRecord objects."""
    papers = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                data = json.loads(line)
                # Reconstruct authors list
                if "authors" in data and isinstance(data["authors"], str):
                    data["authors"] = [a.strip() for a in data["authors"].split(",")]
                papers.append(PaperRecord(**data))
        logger = get_logger(__name__)
        logger.info(f"Loaded {len(papers)} papers from {filepath}")
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to load papers: {e}")
    return papers
