import sys
from workers.celery_app import celery_app

def main():
    print("=" * 60)
    print(" Starting FailureRAG Celery Worker Node")
    print("=" * 60)
    print(" Listening on Queues: high_priority, medium_priority, low_priority")
    print(" Worker Concurrency: 2 (Optimized for Free-Tier APIs)")
    print("\n To monitor live queues, run Flower in a separate terminal:")
    print("   celery -A workers.celery_app flower --port=5555")
    print("-" * 60)
    print(" Starting up...\n")

    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '--queues=high_priority,medium_priority,low_priority'
    ])

if __name__ == "__main__":
    main()
