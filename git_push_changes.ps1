# PowerShell script to add, commit, and push the Self-Learning & Self-Healing RAG changes to GitHub.

Write-Host "Checking git status..." -ForegroundColor Cyan
git status

Write-Host "`nAdding modified files..." -ForegroundColor Cyan
git add CHANGELOG.md WALKTHROUGH.md
git add ingestion/chunker.py database/qdrant_client.py database/neo4j_client.py
git add agents/agent1_retrieval.py agents/agent2_evaluator.py agents/agent7_generator.py agents/models.py
git add api/routes/chat.py

Write-Host "`nCommitting changes..." -ForegroundColor Cyan
git commit -m "Feat: unified citation metadata mapping and multi-layered latency optimizations in hot path"

Write-Host "`nPushing changes to GitHub..." -ForegroundColor Cyan
git push

Write-Host "`nChanges successfully pushed to GitHub!" -ForegroundColor Green
