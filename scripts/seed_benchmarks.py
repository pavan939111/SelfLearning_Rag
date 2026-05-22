import sys
import os

# Append workspace path to system path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from database.supabase_client import SupabaseManager
from utils.logger import get_logger

logger = get_logger(__name__)

BENCHMARK_QUESTIONS = [
    # 1. IMMUNOTHERAPY
    {
        "question_id": "bq_001",
        "question": "What is the mechanism of action of pembrolizumab?",
        "expected_answer": "PD-1 inhibitor that blocks PD-1/PD-L1 interaction",
        "topic_cluster": "immunotherapy",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_002",
        "question": "What is the overall survival benefit of nivolumab in NSCLC?",
        "expected_answer": "Improved OS compared to docetaxel in second line",
        "topic_cluster": "immunotherapy",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_003",
        "question": "What are the main immune-related adverse events of checkpoint inhibitors?",
        "expected_answer": "Colitis, pneumonitis, hepatitis, endocrinopathies",
        "topic_cluster": "immunotherapy",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_004",
        "question": "What is CAR-T cell therapy used for?",
        "expected_answer": "Hematologic malignancies including ALL and DLBCL",
        "topic_cluster": "immunotherapy",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_005",
        "question": "What is PD-L1 expression threshold for pembrolizumab monotherapy?",
        "expected_answer": "TPS >= 50% for first-line monotherapy in NSCLC",
        "topic_cluster": "immunotherapy",
        "difficulty": "easy",
        "source_pmid": ""
    },

    # 2. DRUG INTERACTIONS
    {
        "question_id": "bq_006",
        "question": "What drugs are metabolized by CYP3A4?",
        "expected_answer": "Statins, benzodiazepines, many chemotherapy agents",
        "topic_cluster": "drug_interactions",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_007",
        "question": "What is the mechanism of warfarin drug interactions?",
        "expected_answer": "CYP2C9 inhibition or induction affecting metabolism",
        "topic_cluster": "drug_interactions",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_008",
        "question": "What is polypharmacy and why is it risky?",
        "expected_answer": "Multiple medications increasing adverse event risk",
        "topic_cluster": "drug_interactions",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_009",
        "question": "How does grapefruit affect drug metabolism?",
        "expected_answer": "Inhibits CYP3A4 in gut wall increasing drug levels",
        "topic_cluster": "drug_interactions",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_010",
        "question": "What class of drugs inhibits proton pumps?",
        "expected_answer": "PPIs like omeprazole reduce gastric acid",
        "topic_cluster": "drug_interactions",
        "difficulty": "easy",
        "source_pmid": ""
    },

    # 3. GENOMICS
    {
        "question_id": "bq_011",
        "question": "What is CRISPR-Cas9 used for?",
        "expected_answer": "Precise gene editing by RNA-guided DNA cutting",
        "topic_cluster": "genomics",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_012",
        "question": "What is a single nucleotide polymorphism?",
        "expected_answer": "Single base pair variation in DNA sequence",
        "topic_cluster": "genomics",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_013",
        "question": "What does RNA sequencing measure?",
        "expected_answer": "Gene expression levels across transcriptome",
        "topic_cluster": "genomics",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_014",
        "question": "What is the significance of BRCA mutations?",
        "expected_answer": "Increased risk of breast and ovarian cancer",
        "topic_cluster": "genomics",
        "difficulty": "easy",
        "source_pmid": ""
    },
    {
        "question_id": "bq_015",
        "question": "What is epigenetics?",
        "expected_answer": "Heritable changes in gene expression without DNA sequence change",
        "topic_cluster": "genomics",
        "difficulty": "easy",
        "source_pmid": ""
    }
]

def seed():
    print("="*60)
    print("          FAILURERAG BENCHMARK SEED SCRIPT")
    print("="*60)
    
    # Initialize Supabase client
    supabase_mgr = SupabaseManager()
    if not supabase_mgr.client:
        print("Error: Supabase client could not be initialized!")
        return

    print("Seeding questions to benchmark_questions table in Supabase...")
    
    success_count = 0
    for q_data in BENCHMARK_QUESTIONS:
        try:
            # We use upsert so that it is safe to run repeatedly.
            # Upsert will match on the unique key ('question_id').
            res = supabase_mgr.client.table("benchmark_questions").upsert(
                q_data,
                on_conflict="question_id"
            ).execute()
            
            if res.data:
                print(f"  [SUCCESS] Seeded {q_data['question_id']}: '{q_data['question'][:40]}...'")
                success_count += 1
            else:
                print(f"  [FAILED] Could not seed {q_data['question_id']}")
        except Exception as e:
            print(f"  [ERROR] Exception seeding {q_data['question_id']}: {e}")
            print("  Note: Please make sure the benchmark_questions table is created in Supabase SQL editor.")
            
    print("="*60)
    print(f"Seed process finished. Successfully seeded {success_count}/{len(BENCHMARK_QUESTIONS)} questions.")
    print("="*60)

if __name__ == "__main__":
    seed()
