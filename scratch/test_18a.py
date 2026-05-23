from agents.stream_monitor import StreamMonitor

monitor = StreamMonitor()

print('Running targeted sweep for one cluster...')
print('(This fetches real papers from PubMed)')
print()

# Run a small version of the sweep
# Just one cluster, one query
results = {
    'papers_found': 0,
    'papers_ingested': 0,
    'papers_rejected': 0
}

query = 'pembrolizumab NSCLC 2024'
papers = monitor.fetcher.search_pmids(query, 3, 'immunotherapy')
print(f'PMIDs found: {papers}')

for pmid in papers[:2]:
    raw = monitor.fetcher.fetch_abstracts_batch([pmid])
    if raw:
        paper = monitor.fetcher.parse_article(raw[0], 'immunotherapy')
        if paper:
            result = monitor.verifier.verify(paper)
            print(f'Paper {pmid}: {"PASS" if result.passed else "SKIP"}')
            if result.passed:
                print(f'  Rule: {result.ingestion_instructions.get("rule_matched")}')

print('Phase 18A COMPLETE')
