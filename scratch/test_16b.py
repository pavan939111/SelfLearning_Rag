import httpx

url = 'http://localhost:8000/chat'

session_id = 'test-followup-001'

# Turn 1 - establish context
print('Sending Turn 1...')
r1 = httpx.post(url, json={
    'session_id': session_id,
    'query': 'What are the main checkpoint inhibitors used in NSCLC?'
}, timeout=120)
print(f'Turn 1 status: {r1.status_code}')

# Turn 2 - follow-up
print('Sending Turn 2...')
r2 = httpx.post(url, json={
    'session_id': session_id,
    'query': 'Tell me more about the first one you mentioned'
}, timeout=120)
print(f'Turn 2 status: {r2.status_code}')
d2 = r2.json()
print(f'Follow-up resolved: {d2.get("follow_up_resolved")}')
print(f'Resolved query: {d2.get("resolved_query")}')
print(f'Answer preview: {d2.get("answer", "")[:150]}')
print('Phase 16B COMPLETE')
