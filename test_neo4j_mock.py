import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Ensure the workspace is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from database.neo4j_client import Neo4jManager
from ingestion.pipeline import IngestionPipeline, IngestionStats, PaperRecord
from scripts.backfill_neo4j import backfill

class TestNeo4jOperations(unittest.TestCase):
    def setUp(self):
        # Patch the GraphDatabase.driver call inside __init__
        self.driver_patcher = patch('database.neo4j_client.GraphDatabase.driver')
        self.mock_driver_class = self.driver_patcher.start()
        self.mock_driver = MagicMock()
        self.mock_driver_class.return_value = self.mock_driver
        
        # Instantiate manager
        self.neo4j = Neo4jManager()
        
    def tearDown(self):
        self.driver_patcher.stop()

    def test_init_and_close(self):
        self.mock_driver_class.assert_called_once()
        self.neo4j.close()
        self.mock_driver.close.assert_called_once()

    def test_create_paper_node_dict(self):
        # Mock session and run
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        paper_dict = {
            "paper_id": "PMC12345",
            "title": "Immunotherapy treatments in lung cancer",
            "year": 2024,
            "journal": "Nature Medicine",
            "topic_cluster": "immunotherapy",
            "evidence_level": "Level 1a",
            "ingestion_date": "2026-05-22",
            "freshness_score": 0.95,
            "contradiction_flag": False
        }
        
        res = self.neo4j.create_paper_node(paper_dict)
        self.assertTrue(res)
        
        # Verify cypher execution
        mock_session.run.assert_called_once()
        cypher_arg = mock_session.run.call_args[0][0]
        params_arg = mock_session.run.call_args[1]
        
        self.assertIn("MERGE (p:Paper {paper_id: $paper_id})", cypher_arg)
        self.assertIn("SET p.title = $title", cypher_arg)
        self.assertEqual(params_arg["paper_id"], "PMC12345")
        self.assertEqual(params_arg["year"], 2024)
        self.assertEqual(params_arg["contradiction_flag"], False)

    def test_create_paper_node_object(self):
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        paper_obj = PaperRecord(
            paper_id="PMC67890",
            title="Cytochrome P450 interactions with drug combinations",
            authors=["Author A", "Author B"],
            journal="Science",
            year=2023,
            abstract="Some abstract",
            doi="10.1126/science.123",
            topic_cluster="drug_interactions",
            evidence_level="Level 2b",
            ingestion_date="2026-05-22",
            freshness_score=0.88,
            contradiction_flag=True,
            has_full_text=False
        )
        
        res = self.neo4j.create_paper_node(paper_obj)
        self.assertTrue(res)
        
        # Verify params mapping
        params_arg = mock_session.run.call_args[1]
        self.assertEqual(params_arg["paper_id"], "PMC67890")
        self.assertEqual(params_arg["year"], 2023)
        self.assertEqual(params_arg["contradiction_flag"], True)

    def test_create_paper_node_error_handling(self):
        # Force an exception during session.run
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Cypher query error")
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        paper_dict = {"paper_id": "PMC999"}
        res = self.neo4j.create_paper_node(paper_dict)
        
        # Should return False instead of raising an uncaught exception
        self.assertFalse(res)

    def test_create_papers_batch(self):
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        # Create a mock query result that returns a single record with "count"
        mock_result = MagicMock()
        mock_record = {"count": 3}
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        papers = [
            {"paper_id": f"PMC_B_{i}", "title": f"Paper B {i}", "year": 2024}
            for i in range(3)
        ]
        
        success_count = self.neo4j.create_papers_batch(papers)
        
        self.assertEqual(success_count, 3)
        mock_session.run.assert_called_once()
        cypher_arg = mock_session.run.call_args[0][0]
        params_arg = mock_session.run.call_args[1]
        
        self.assertIn("UNWIND $papers AS p_data", cypher_arg)
        self.assertIn("MERGE (p:Paper {paper_id: p_data.paper_id})", cypher_arg)
        self.assertEqual(len(params_arg["papers"]), 3)
        self.assertEqual(params_arg["papers"][0]["paper_id"], "PMC_B_0")

    def test_create_papers_batch_multiple_groups(self):
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 50}
        mock_session.run.return_value = mock_result
        
        # 75 papers should trigger 2 batches (50 and 25)
        papers = [
            {"paper_id": f"PMC_B_{i}", "title": f"Paper B {i}", "year": 2024}
            for i in range(75)
        ]
        
        success_count = self.neo4j.create_papers_batch(papers)
        
        # Since single.return_value is {"count": 50} for each call, total count = 100
        self.assertEqual(success_count, 100)
        self.assertEqual(mock_session.run.call_count, 2)

    def test_get_paper_count(self):
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.single.return_value = {"count": 125}
        mock_session.run.return_value = mock_result
        
        count = self.neo4j.get_paper_count()
        self.assertEqual(count, 125)
        mock_session.run.assert_called_once_with("MATCH (p:Paper) RETURN count(p) as count")

    def test_get_paper_count_error(self):
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Driver error")
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        count = self.neo4j.get_paper_count()
        self.assertEqual(count, 0) # Should return 0 on error

    def test_create_topic_cluster_nodes(self):
        mock_session = MagicMock()
        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        
        res = self.neo4j.create_topic_cluster_nodes()
        self.assertTrue(res)
        
        # Should have called session.run 4 times (3 for topic creation, 1 for relationships)
        self.assertEqual(mock_session.run.call_count, 4)
        
        calls = [call[0][0] for call in mock_session.run.call_args_list]
        self.assertTrue(any("immunotherapy" in c for c in calls))
        self.assertTrue(any("drug_interactions" in c for c in calls))
        self.assertTrue(any("genomics" in c for c in calls))
        self.assertTrue(any("MATCH (p:Paper), (c:TopicCluster)" in c for c in calls))


class TestPipelineNeo4jIntegration(unittest.TestCase):
    @patch('database.neo4j_client.GraphDatabase.driver')
    @patch('ingestion.pipeline.QdrantManager')
    @patch('ingestion.pipeline.SupabaseManager')
    @patch('ingestion.pipeline.BiomedicalEmbedder')
    @patch('agents.agent5a_verifier.Agent5AVerifier')
    def test_pipeline_does_not_crash_on_neo4j_failure(self, mock_verifier_class, mock_emb_class, mock_supa_class, mock_qd_class, mock_driver_class):
        # Configure Mocks
        mock_verifier = MagicMock()
        mock_verifier_class.return_value = mock_verifier
        
        mock_result = MagicMock()
        mock_result.passed = True
        mock_result.ingestion_instructions = {
            "topic_cluster": "genomics",
            "evidence_level": "Level 1c",
            "contradiction_suspected": False
        }
        mock_verifier.verify.return_value = mock_result
        
        # Force Neo4j manager to raise exception during paper node creation
        mock_driver = MagicMock()
        mock_driver_class.return_value = mock_driver
        mock_session = MagicMock()
        mock_session.run.side_effect = Exception("Neo4j is offline!")
        mock_driver.session.return_value.__enter__.return_value = mock_session
        
        pipeline = IngestionPipeline()
        
        # Let's mock chunking response
        pipeline.chunker.chunk_paper = MagicMock(return_value={
            "document": ["chunk1"],
            "sections": ["chunk2"],
            "semantic": ["chunk3"],
            "propositions": ["chunk4"]
        })
        
        # Mock embedder
        pipeline.embedder.embed_chunks = MagicMock(return_value=[[0.1]*768])
        
        # Test paper
        paper = PaperRecord(
            paper_id="PMC_FAIL",
            title="Genomics paper",
            authors=["Author 1"],
            journal="Nature",
            year=2025,
            abstract="Ab",
            doi="10.1038/nature.456",
            topic_cluster="genomics",
            evidence_level="Level 1c",
            ingestion_date="2026-05-22",
            freshness_score=1.0,
            contradiction_flag=False,
            has_full_text=False
        )
        
        stats = IngestionStats()
        
        # Run process_paper. It should succeed (return True) even if Neo4j raises exception
        res = pipeline.process_paper(paper, stats)
        
        self.assertTrue(res)
        self.assertEqual(stats.successful_papers, 1)
        self.assertEqual(stats.failed_papers, 0)


class TestBackfillScript(unittest.TestCase):
    @patch('scripts.backfill_neo4j.load_papers')
    @patch('scripts.backfill_neo4j.Neo4jManager')
    @patch('os.path.exists')
    def test_backfill_runs_correctly(self, mock_exists, mock_neo4j_class, mock_load):
        # 1. Mock file exists
        mock_exists.return_value = True
        
        # 2. Mock loaded papers
        papers = [
            PaperRecord(
                paper_id=f"PMC_BF_{i}",
                title=f"Title {i}",
                authors=["Author"],
                journal="Journal",
                year=2024,
                abstract="",
                doi="",
                topic_cluster="immunotherapy",
                evidence_level="Level 1",
                ingestion_date="2026-05-22",
                freshness_score=1.0,
                contradiction_flag=False,
                has_full_text=False
            )
            for i in range(120) # 120 papers
        ]
        mock_load.return_value = papers
        
        # 3. Mock Neo4j manager
        mock_neo4j = MagicMock()
        mock_neo4j.driver = MagicMock()
        mock_neo4j.get_paper_count.side_effect = [10, 130] # 10 before, 130 after
        mock_neo4j.create_papers_batch.return_value = 50 # returns batch size on mock call
        mock_neo4j_class.return_value = mock_neo4j
        
        # Mock stdout to check progress prints
        with patch('sys.stdout', new_callable=mock_open()) as mock_stdout:
            backfill()
            
        # Verify batching calls
        # 120 papers in batches of 50 -> 3 batches (50, 50, 20)
        self.assertEqual(mock_neo4j.create_papers_batch.call_count, 3)
        mock_neo4j.create_topic_cluster_nodes.assert_called_once()
        mock_neo4j.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
