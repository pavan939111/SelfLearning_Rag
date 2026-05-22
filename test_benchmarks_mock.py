import unittest
from unittest.mock import MagicMock, patch, mock_open
import sys
import os

# Ensure the workspace is in the python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from scripts.seed_benchmarks import seed, BENCHMARK_QUESTIONS
from scripts.run_benchmark import run_benchmark

class TestBenchmarkInfrastructure(unittest.TestCase):

    @patch('scripts.seed_benchmarks.SupabaseManager')
    def test_seed_benchmarks(self, mock_supabase_class):
        # Configure mock Supabase Client
        mock_supabase_mgr = MagicMock()
        mock_supabase_client = MagicMock()
        mock_supabase_mgr.client = mock_supabase_client
        mock_supabase_class.return_value = mock_supabase_mgr
        
        # Configure table and upsert mock
        mock_table = MagicMock()
        mock_supabase_client.table.return_value = mock_table
        mock_upsert_res = MagicMock()
        mock_upsert_res.data = [{"id": 1}]
        mock_table.upsert.return_value = mock_upsert_res
        
        # Mock stdout to check prints without polluting terminal
        with patch('sys.stdout', new_callable=mock_open()) as mock_stdout:
            seed()
            
        # Assertions
        # Should call table("benchmark_questions") and upsert 15 times
        self.assertEqual(mock_supabase_client.table.call_count, 15)
        mock_supabase_client.table.assert_called_with("benchmark_questions")
        self.assertEqual(mock_table.upsert.call_count, 15)
        
        # Verify the structure of the seeded questions
        self.assertEqual(len(BENCHMARK_QUESTIONS), 15)
        for i, q in enumerate(BENCHMARK_QUESTIONS):
            q_id = f"bq_{i+1:03d}"
            self.assertEqual(q["question_id"], q_id)
            self.assertEqual(q["difficulty"], "easy")
            self.assertEqual(q["source_pmid"], "")
            
            # Check cluster distribution
            if i < 5:
                self.assertEqual(q["topic_cluster"], "immunotherapy")
            elif i < 10:
                self.assertEqual(q["topic_cluster"], "drug_interactions")
            else:
                self.assertEqual(q["topic_cluster"], "genomics")

    @patch('scripts.run_benchmark.requests')
    @patch('scripts.run_benchmark.SupabaseManager')
    def test_run_benchmark_engine(self, mock_supabase_class, mock_requests):
        # 1. Mock Supabase Client and Table Queries
        mock_supabase_mgr = MagicMock()
        mock_supabase_client = MagicMock()
        mock_supabase_mgr.client = mock_supabase_client
        mock_supabase_class.return_value = mock_supabase_mgr
        
        # Questions list to return from mock select()
        mock_questions = [
            {
                "question_id": f"bq_{i+1:03d}",
                "question": f"Question {i+1}",
                "expected_answer": f"Expected {i+1}",
                "topic_cluster": "immunotherapy" if i < 5 else "drug_interactions" if i < 10 else "genomics",
                "difficulty": "easy"
            }
            for i in range(15)
        ]
        
        mock_questions_table = MagicMock()
        mock_select_res = MagicMock()
        mock_select_res.data = mock_questions
        mock_questions_table.select.return_value.order.return_value.execute.return_value = mock_select_res
        
        mock_results_table = MagicMock()
        mock_insert_res = MagicMock()
        mock_insert_res.data = [{"id": 1}]
        mock_results_table.insert.return_value.execute.return_value = mock_insert_res
        
        # Configure table() route mappings
        def table_side_effect(table_name):
            if table_name == "benchmark_questions":
                return mock_questions_table
            elif table_name == "benchmark_results":
                return mock_results_table
            return MagicMock()
            
        mock_supabase_client.table.side_effect = table_side_effect
        
        # 2. Mock HTTP requests to localhost server
        # Health check
        mock_health_resp = MagicMock()
        mock_health_resp.status_code = 200
        mock_requests.get.return_value = mock_health_resp
        
        # Varying /chat responses to test metrics aggregation and agent2_passed logic
        chat_responses = []
        for i in range(15):
            mock_resp = MagicMock()
            
            # Vary status, cache, cycle, confidence values
            if i % 5 == 0:
                # Cache hit: cycle_ran=False, cache_hit=True, confidence=0.9
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "answer": f"Answer {i+1}",
                    "confidence": 0.9,
                    "cycle_ran": False,
                    "cycle_exit_reason": "",
                    "cache_hit": True,
                    "processing_time_ms": 150
                }
            elif i % 5 == 1:
                # Initial pass: cycle_ran=False, cache_hit=False, confidence=0.8
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "answer": f"Answer {i+1}",
                    "confidence": 0.8,
                    "cycle_ran": False,
                    "cycle_exit_reason": "",
                    "cache_hit": False,
                    "processing_time_ms": 1200
                }
            elif i % 5 == 2:
                # Cycle ran & passed: cycle_ran=True, cycle_exit_reason="agent2_passed", confidence=0.75
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "answer": f"Answer {i+1}",
                    "confidence": 0.75,
                    "cycle_ran": True,
                    "cycle_exit_reason": "agent2_passed",
                    "cache_hit": False,
                    "processing_time_ms": 4500
                }
            elif i % 5 == 3:
                # Cycle ran & failed: cycle_ran=True, cycle_exit_reason="max_cycles", confidence=0.4
                mock_resp.status_code = 200
                mock_resp.json.return_value = {
                    "answer": f"Answer {i+1}",
                    "confidence": 0.4,
                    "cycle_ran": True,
                    "cycle_exit_reason": "max_cycles",
                    "cache_hit": False,
                    "processing_time_ms": 9500
                }
            else:
                # Server Error (HTTP 500)
                mock_resp.status_code = 500
                mock_resp.json.return_value = {}
                
            chat_responses.append(mock_resp)
            
        mock_requests.post.side_effect = chat_responses

        # Mock stdout to verify summary report formatting
        mock_stdout = MagicMock()
        with patch('sys.stdout', mock_stdout):
            run_benchmark()
            
        # Assertions
        # 1. Verified fetching
        mock_supabase_client.table.assert_any_call("benchmark_questions")
        
        # 2. Verified HTTP request calls
        # 1 health check, 15 posts to /api/chat
        mock_requests.get.assert_called_once_with("http://localhost:8000/api/health", timeout=2)
        self.assertEqual(mock_requests.post.call_count, 15)
        
        # 3. Verified Supabase insertions into benchmark_results
        self.assertEqual(mock_results_table.insert.call_count, 15)
        
        # Inspect parameters of one insertion call to verify calculations
        # Question 1 (i=0): Cache hit -> agent2_passed=True
        first_insert_data = mock_results_table.insert.call_args_list[0][0][0]
        self.assertEqual(first_insert_data["question_id"], "bq_001")
        self.assertEqual(first_insert_data["agent2_passed"], True)
        self.assertEqual(first_insert_data["cache_hit"], True)
        self.assertEqual(first_insert_data["cycle_ran"], False)
        
        # Question 4 (i=3): Cycle ran & failed -> agent2_passed=False
        failed_insert_data = mock_results_table.insert.call_args_list[3][0][0]
        self.assertEqual(failed_insert_data["question_id"], "bq_004")
        self.assertEqual(failed_insert_data["agent2_passed"], False)
        self.assertEqual(failed_insert_data["cache_hit"], False)
        self.assertEqual(failed_insert_data["cycle_ran"], True)
        
        # Question 5 (i=4): HTTP 500 -> agent2_passed=False
        err_insert_data = mock_results_table.insert.call_args_list[4][0][0]
        self.assertEqual(err_insert_data["question_id"], "bq_005")
        self.assertEqual(err_insert_data["agent2_passed"], False)
        self.assertEqual(err_insert_data["generated_answer"], "HTTP Error 500")

        # 4. Verify terminal output contains the expected summary report fields
        stdout_calls = [call[0][0] for call in mock_stdout.write.call_args_list if call[0]]
        full_output = "".join(stdout_calls)
        
        self.assertIn("Summary report:", full_output)
        self.assertIn("Total questions: 15", full_output)
        self.assertIn("Agent 2 pass rate: 9/15", full_output) # (3 cache hits, 3 initial passes, 3 cycle passes) = 9 passes
        self.assertIn("Average confidence:", full_output)
        self.assertIn("Average response time:", full_output)
        self.assertIn("Cache hits: 3/15", full_output)
        self.assertIn("Cycle triggered: 6/15", full_output) # (3 cycle passes, 3 cycle fails) = 6 triggered
        self.assertIn("BENCHMARK BASELINE RECORDED", full_output)


if __name__ == "__main__":
    unittest.main()
