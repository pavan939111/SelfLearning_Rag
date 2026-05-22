from agents.conversation_memory import ConversationMemory
import uuid

def test():
    memory = ConversationMemory()
    session_id = str(uuid.uuid4())
    print(f'Session: {session_id[:8]}...')

    # Simulate a conversation
    memory.add_turn(session_id, 'user', 
        'What is pembrolizumab?', 'simple_factual', 0.0)
    memory.add_turn(session_id, 'assistant',
        'Pembrolizumab is a PD-1 inhibitor used in cancer treatment (Chen 2023).', 
        '', 0.82)
    memory.add_turn(session_id, 'user',
        'What are its side effects?', 'simple_factual', 0.0)
    memory.add_turn(session_id, 'assistant',
        'Common side effects include fatigue and immune reactions (Smith 2022).',
        '', 0.78)

    history = memory.get_history_for_agent7(session_id)
    print(f'History turns: {len(history)}')
    for h in history:
        print(f'  [{h["role"]}]: {h["content"][:60]}')

    memory.clear_session(session_id)
    print('Session cleared OK')
    print('Phase 9B PASSED')

if __name__ == "__main__":
    test()
