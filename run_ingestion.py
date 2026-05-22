import sys
import os
import json
from ingestion.pipeline import IngestionPipeline, IngestionStats
from ingestion.fetcher import PubMedFetcher, save_papers
from utils.logger import get_logger

logger = get_logger(__name__)

def main():
    print("\n" + "="*50)
    print("      FAILURERAG - MASTER INGESTION PIPELINE")
    print("="*50)

    pipeline = IngestionPipeline()
    papers_path = "logs/fetched_papers.jsonl"
    use_existing = False

    if os.path.exists(papers_path):
        # In a headless environment, we might want to default to 'y' or handle this differently
        # But for local dev as requested:
        try:
            ans = input(f"\nFound existing papers file '{papers_path}'. Use it? (y/n): ").lower()
            if ans == 'y':
                use_existing = True
        except EOFError:
            # Handle non-interactive environments
            print("\nNon-interactive environment detected. Defaulting to using existing file.")
            use_existing = True

    try:
        # 1. Fetching (if needed)
        if not use_existing:
            print("\nStep 1: Fetching fresh papers from PubMed...")
            fetcher = PubMedFetcher()
            # The user requested 600 per cluster
            papers = fetcher.fetch_all_clusters(papers_per_cluster=600)
            os.makedirs("logs", exist_ok=True)
            save_papers(papers, papers_path)
            print(f"Fetched {len(papers)} papers and saved to {papers_path}")
        else:
            print("\nStep 1: Using existing papers file.")

        # 2. Running Pipeline
        print("\nStep 2: Starting Ingestion (Chunking -> Embedding -> Indexing)...")
        # pipeline.run handles collection setup, loading papers, checkpointing, and stats
        stats = pipeline.run(
            papers_file=papers_path,
            log_every=25
        )

        # 3. Final Summary
        summary = stats.to_dict()
        
        banner = "\n" + "="*48 + "\n"
        banner += "FAILURERAG INGESTION COMPLETE\n"
        banner += "="*48 + "\n"
        banner += f"Papers processed:    {summary['total_papers']}\n"
        banner += f"Successful:          {summary['successful_papers']}\n"
        banner += f"Failed:              {summary['failed_papers']}\n"
        banner += "\nChunks inserted:\n"
        banner += f"  document:          {summary['inserted']['document']}\n"
        banner += f"  section:           {summary['inserted']['section']}\n"
        banner += f"  semantic:          {summary['inserted']['semantic']}\n"
        banner += f"  proposition:       {summary['inserted']['proposition']}\n"
        banner += f"\nDuration: {summary['duration_seconds']/60:.1f} minutes\n"
        banner += "="*48 + "\n"

        print(banner)

        # Save summary to file
        with open("logs/ingestion_summary.txt", "w") as f:
            f.write(banner)
        print(f"Summary saved to logs/ingestion_summary.txt")

    except KeyboardInterrupt:
        print("\n\nIngestion interrupted. Checkpoint saved. Run again to resume.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nAn error occurred: {e}")
        logger.error(f"Pipeline error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
