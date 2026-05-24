ADVERSARIAL_QUESTIONS = [
  {
    "question": "What is the exact ORR of pembrolizumab in PD-L1 negative NSCLC patients?",
    "question_type": "factual_recall",
    "difficulty": "adversarial",
    "note": "Tests corpus coverage of specific subgroup"
  },
  {
    "question": "How does pembrolizumab compare to nivolumab in PD-L1 low patients?",
    "question_type": "comparative",
    "difficulty": "adversarial",
    "note": "Tests whether system admits limited evidence"
  },
  {
    "question": "What was approved by FDA for NSCLC last month?",
    "question_type": "temporal",
    "difficulty": "adversarial",
    "note": "Tests live fetch - corpus cannot answer"
  },
  {
    "question": "What is the mechanism of acquired resistance to pembrolizumab?",
    "question_type": "multi_hop",
    "difficulty": "adversarial",
    "note": "Tests multi-hop across mechanism papers"
  },
  {
    "question": "Which CYP450 enzyme metabolizes both warfarin and fluconazole?",
    "question_type": "factual_recall",
    "difficulty": "adversarial",
    "note": "Tests specific drug interaction knowledge"
  },
  {
    "question": "What is the difference between SNP and indel?",
    "question_type": "comparative",
    "difficulty": "easy",
    "note": "Baseline - should always pass"
  },
  {
    "question": "Is CRISPR base editing approved for clinical use in 2024?",
    "question_type": "temporal",
    "difficulty": "adversarial",
    "note": "Requires live fetch for current status"
  },
  {
    "question": "How do checkpoint inhibitors cause immune-related adverse events and what organs are most affected?",
    "question_type": "multi_hop",
    "difficulty": "hard",
    "note": "Tests multi-hop mechanism reasoning"
  },
  {
    "question": "What genomic biomarkers predict response to PD-1 inhibitors?",
    "question_type": "exploratory",
    "difficulty": "hard",
    "note": "Tests broad exploratory retrieval"
  },
  {
    "question": "Compare overall survival benefit of pembrolizumab vs nivolumab vs atezolizumab in NSCLC",
    "question_type": "comparative",
    "difficulty": "adversarial",
    "note": "Three-way comparison - tests parallel retrieval"
  }
]
