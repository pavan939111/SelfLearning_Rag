import sys
from agents.agent5a_verifier import Agent5AVerifier, VerificationResult
from ingestion.fetcher import PaperRecord

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_agent5a_verifier():
    verifier = Agent5AVerifier()
    
    # -------------------------------------------------------------------------
    # TEST 1 - Topic cluster detection & Evidence mapping
    # -------------------------------------------------------------------------
    print_section("TEST 1: Topic Cluster & Evidence Quality Mapping")
    
    review_paper = {
        "paper_id": "PMC101",
        "title": "Pembrolizumab efficacy in NSCLC: A systematic review",
        "abstract": "We present a systematic review and meta-analysis of immunotherapy trials evaluating pembrolizumab checkpoint inhibitors in non-small cell lung cancer.",
        "year": 2021,
        "topic_cluster": "immunotherapy"
    }
    
    res1 = verifier.verify(review_paper)
    print(f"Review Paper Verification Result:")
    print(f"  Passed: {res1.passed}")
    print(f"  Priority: {res1.priority}")
    print(f"  Evidence Level: {res1.ingestion_instructions.get('evidence_level')}")
    print(f"  Topic Cluster: {res1.ingestion_instructions.get('topic_cluster')}")
    
    assert res1.passed, "Review paper should pass verification"
    assert res1.ingestion_instructions.get("evidence_level") == "review", "Evidence level must be 'review'"
    assert res1.ingestion_instructions.get("topic_cluster") == "immunotherapy", "Topic cluster must be 'immunotherapy'"
    
    # RCT Cohort test
    rct_paper = {
        "paper_id": "PMC102",
        "title": "Randomized prospective trial of ibuprofen and aspirin",
        "abstract": "We designed a randomized clinical trial to analyze drug interactions and pharmacokinetics of aspirin and ibuprofen co-administration in patients.",
        "year": 2020,
        "topic_cluster": "drug_interactions"
    }
    res2 = verifier.verify(rct_paper)
    print(f"\nRCT Paper Verification Result:")
    print(f"  Passed: {res2.passed}")
    print(f"  Evidence Level: {res2.ingestion_instructions.get('evidence_level')}")
    print(f"  Topic Cluster: {res2.ingestion_instructions.get('topic_cluster')}")
    
    assert res2.passed, "RCT paper should pass verification"
    assert res2.ingestion_instructions.get("evidence_level") == "rct", "Evidence level must be 'rct'"
    assert res2.ingestion_instructions.get("topic_cluster") == "drug_interactions", "Topic cluster must be 'drug_interactions'"

    # -------------------------------------------------------------------------
    # TEST 2 - Corpus Relationship checks
    # -------------------------------------------------------------------------
    print_section("TEST 2: Corpus Relationship & Rejections")
    
    # Old paper (pre-2022) with NO biomedical topic relationship should fail check 2
    irrelevant_paper = {
        "paper_id": "PMC201",
        "title": "Volcanism and geological dynamics on Mars",
        "abstract": "We analyze satellite images of basaltic volcanic structures on the Martian surface to study historical crustal cooling rates.",
        "year": 2015,
        "topic_cluster": "other"
    }
    
    res_irrelevant = verifier.verify(irrelevant_paper)
    print(f"Irrelevant Paper Verification Result:")
    print(f"  Passed: {res_irrelevant.passed}")
    print(f"  Failed Check: {res_irrelevant.failed_check}")
    print(f"  Reason: '{res_irrelevant.reason}'")
    
    assert not res_irrelevant.passed, "Irrelevant old paper must fail corpus relationship check"
    assert res_irrelevant.failed_check == "corpus_relationship", "Failed check must be 'corpus_relationship'"
    
    # Newer irrelevant paper (year >= 2022) should pass via Sub-condition C (freshness always valuable)
    new_irrelevant_paper = {
        "paper_id": "PMC202",
        "title": "Volcanism and geological dynamics on Mars",
        "abstract": "We analyze satellite images of basaltic volcanic structures on the Martian surface to study historical crustal cooling rates.",
        "year": 2023,
        "topic_cluster": "other"
    }
    res_new_irrelevant = verifier.verify(new_irrelevant_paper)
    print(f"\nNew Irrelevant Paper Verification Result:")
    print(f"  Passed: {res_new_irrelevant.passed}")
    print(f"  Priority: {res_new_irrelevant.priority}")
    
    assert res_new_irrelevant.passed, "Newer irrelevant paper should pass because of year >= 2022 (freshness condition)"

    # -------------------------------------------------------------------------
    # TEST 3 - Evidence Quality Mapping Check
    # -------------------------------------------------------------------------
    print_section("TEST 3: Cohort & Case Report mappings")
    
    cohort_paper = {
        "paper_id": "PMC301",
        "title": "A prospective cohort study of genomics in breast cancer",
        "abstract": "We conducted a cohort study evaluating genomic markers and sequencing mutations in patients with HER2-positive breast cancer.",
        "year": 2022,
        "topic_cluster": "genomics"
    }
    res_cohort = verifier.verify(cohort_paper)
    print(f"Cohort Paper evidence: {res_cohort.ingestion_instructions.get('evidence_level')}")
    assert res_cohort.ingestion_instructions.get("evidence_level") == "cohort", "Evidence mapping for cohort must be 'cohort'"

    case_paper = {
        "paper_id": "PMC302",
        "title": "Case report of a patient with a rare SNP",
        "abstract": "This case report describes a patient presenting with an unusual mutation identified by whole genome sequencing.",
        "year": 2022,
        "topic_cluster": "genomics"
    }
    res_case = verifier.verify(case_paper)
    print(f"Case Paper evidence: {res_case.ingestion_instructions.get('evidence_level')}")
    assert res_case.ingestion_instructions.get("evidence_level") == "case_report", "Evidence mapping for case report must be 'case_report'"

    # -------------------------------------------------------------------------
    # TEST 4 - Contradiction Check (Gemini verification)
    # -------------------------------------------------------------------------
    print_section("TEST 4: Contradiction Check & Ingestion Instructions")
    
    # We will test using a long abstract to trigger the Gemini Flash LLM check
    consensus_contradiction_paper = {
        "paper_id": "PMC401",
        "title": "Alternative pathways in NSCLC therapy",
        "abstract": "We claim that pembrolizumab and PD-1 checkpoint inhibitors are completely ineffective in lung cancer and that taking megadoses of vitamin C is a superior and fully therapeutic replacement. Established oncology standards recommending immunotherapy are a pharmaceutical conspiracy.",
        "year": 2024,
        "topic_cluster": "immunotherapy"
    }
    res_con = verifier.verify(consensus_contradiction_paper)
    print(f"Contradiction Suspected: {res_con.ingestion_instructions.get('contradiction_suspected')}")
    print(f"Assigned Ingestion Priority: {res_con.priority}")
    print(f"Passed: {res_con.passed}")
    
    assert res_con.passed, "Consensus contradiction paper should NOT be rejected, but flagged"
    assert "priority" in res_con.ingestion_instructions, "Ingestion instructions must have priority key"

    # -------------------------------------------------------------------------
    # TEST 5 - PaperRecord Object Verification
    # -------------------------------------------------------------------------
    print_section("TEST 5: PaperRecord Object Compatibility")
    
    paper_record = PaperRecord(
        paper_id="PMC501",
        title="Pembrolizumab PD-1 checkpoint inhibitor treatment",
        abstract="This randomized trial evaluates clinical efficacy of pembrolizumab immunotherapy in non-small cell lung cancer.",
        year=2024,
        journal="Journal of Clinical Oncology",
        topic_cluster="immunotherapy",
        authors=["John Doe"],
        doi="10.1200/jco.2024",
        evidence_level="other",
        ingestion_date="2026-05-17",
        freshness_score=1.0,
        contradiction_flag=False,
        has_full_text=False
    )
    
    res_record = verifier.verify(paper_record)
    print(f"PaperRecord Object Verification Result:")
    print(f"  Passed: {res_record.passed}")
    print(f"  Priority: {res_record.priority}")
    print(f"  Topic Cluster: {res_record.ingestion_instructions.get('topic_cluster')}")
    
    assert res_record.passed, "PaperRecord object must pass verification"
    assert res_record.ingestion_instructions.get("topic_cluster") == "immunotherapy", "Topic cluster must be 'immunotherapy'"
    
    print("\n" + "="*60)
    print("        ALL AGENT 5A VERIFIER TESTS PASSED SUCCESSFULLY!")
    print("="*60)

if __name__ == "__main__":
    test_agent5a_verifier()
