from agents.agent1_retrieval import QueryClassifier

classifier = QueryClassifier()

test_queries = [
    # Should PASS (biomedical)
    'How does pembrolizumab work?',
    'What are drug interactions with warfarin?',
    'What is CRISPR-Cas9 used for?',
    'Compare nivolumab and pembrolizumab in NSCLC',
    'What is PD-L1 expression threshold?',
    
    # Should REJECT (off-topic)
    'What is the best recipe for pasta?',
    'Who won the cricket world cup?',
    'How do I write a Python function?',
    'What is the capital of France?',
    'Tell me a joke',
]

print('Domain validation test:')
print()

passed = 0
rejected = 0

for query in test_queries:
    result = classifier.classify(query)
    status = 'REJECTED' if result.domain_rejected else 'ACCEPTED'
    
    if result.domain_rejected:
        rejected += 1
        print(f'  [{status}] {query}')
        print(f'           Reason: {result.rejection_reason}')
    else:
        passed += 1
        print(f'  [{status}] {query}')
        print(f'           Type: {result.query_type}')
    print()

print(f'Biomedical accepted: {passed}')
print(f'Off-topic rejected:  {rejected}')
print()

if passed == 5 and rejected == 5:
    print('Domain validation WORKING CORRECTLY')
else:
    print('Some queries classified incorrectly')
    print('Check Gemini response parsing')
