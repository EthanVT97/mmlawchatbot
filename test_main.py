import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
import os
import sys

# Add the main module to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app, load_questions_dataset, search_in_dataset, query_gemini_ai

# Test client
client = TestClient(app)

# Mock environment variables for testing
@patch.dict(os.environ, {
    "GOOGLE_API_KEY": "test_api_key",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_KEY": "test_key",
    "ENVIRONMENT": "testing",
    "ALLOWED_ORIGINS": "http://localhost:3000"
})
class TestMMLawChatbot:
    
    def test_health_endpoint(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["environment"] == "testing"
    
    def test_ask_endpoint_validation(self):
        """Test input validation for ask endpoint"""
        # Empty question
        response = client.post("/ask", json={"question": ""})
        assert response.status_code == 422
        
        # Missing question field
        response = client.post("/ask", json={})
        assert response.status_code == 422
        
        # Question too long (over 500 chars)
        long_question = "a" * 501
        response = client.post("/ask", json={"question": long_question})
        assert response.status_code == 422
        
        # Whitespace only question
        response = client.post("/ask", json={"question": "   "})
        assert response.status_code == 422
    
    @patch('main.log_question_to_supabase')
    @patch('main.update_answer_in_supabase')
    @patch('main.search_in_dataset')
    def test_ask_endpoint_dataset_response(self, mock_search, mock_update, mock_log):
        """Test successful response from dataset"""
        # Mock dependencies
        mock_log.return_value = AsyncMock(return_value=True)
        mock_update.return_value = AsyncMock(return_value=True)
        mock_search.return_value = "မြန်မာနိုင်ငံ ဥပဒေအရ ခိုးယူမှုအတွက် သတ်မှတ်အပြစ်..."
        
        response = client.post("/ask", json={
            "question": "ဥပဒေအရ ခိုးယူမှုအပြစ်ဒဏ်"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["source"] == "dataset"
        assert len(data["answer"]) > 0
    
    @patch('main.log_question_to_supabase')
    @patch('main.update_answer_in_supabase')
    @patch('main.search_in_dataset')
    @patch('main.query_gemini_ai')
    def test_ask_endpoint_ai_response(self, mock_gemini, mock_search, mock_update, mock_log):
        """Test successful response from Gemini AI"""
        # Mock dependencies
        mock_log.return_value = AsyncMock(return_value=True)
        mock_update.return_value = AsyncMock(return_value=True)
        mock_search.return_value = None  # No dataset match
        mock_gemini.return_value = AsyncMock(return_value="AI generated answer in Burmese")
        
        response = client.post("/ask", json={
            "question": "အသစ်သောဥပဒေမေးခွန်း"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["source"] == "ai"
    
    @patch('main.log_question_to_supabase')
    @patch('main.update_answer_in_supabase')
    @patch('main.search_in_dataset')
    @patch('main.query_gemini_ai')
    def test_ask_endpoint_fallback_response(self, mock_gemini, mock_search, mock_update, mock_log):
        """Test fallback response when both dataset and AI fail"""
        # Mock dependencies
        mock_log.return_value = AsyncMock(return_value=True)
        mock_update.return_value = AsyncMock(return_value=True)
        mock_search.return_value = None  # No dataset match
        mock_gemini.return_value = AsyncMock(return_value=None)  # AI failed
        
        response = client.post("/ask", json={
            "question": "အမေးခွန်းမရှိ"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert data["source"] == "fallback"
        assert "ဝမ်းနည်းပါတယ်" in data["answer"]  # Fallback message
    
    def test_rate_limiting(self):
        """Test rate limiting (5 requests per minute)"""
        # Mock successful responses to avoid external dependencies
        with patch('main.log_question_to_supabase', return_value=AsyncMock(return_value=True)), \
             patch('main.update_answer_in_supabase', return_value=AsyncMock(return_value=True)), \
             patch('main.search_in_dataset', return_value="Test answer"):
            
            # Make 5 requests (should succeed)
            for i in range(5):
                response = client.post("/ask", json={"question": f"မေးခွန်း {i}"})
                assert response.status_code == 200
            
            # 6th request should be rate limited
            response = client.post("/ask", json={"question": "ထပ်တိုး"})
            assert response.status_code == 429  # Too Many Requests
    
    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.get("/health")
        assert "access-control-allow-origin" in response.headers
    
# Test utility functions
class TestUtilityFunctions:
    
    def test_load_questions_dataset(self):
        """Test YAML dataset loading"""
        # Create a mock YAML file content
        mock_yaml_content = [
            {"question": "မေးခွန်း ၁", "answer": "အဖြေ ၁"},
            {"question": "မေးခွန်း ၂", "answer": "အဖြေ ၂"}
        ]
        
        with patch('builtins.open'), \
             patch('yaml.safe_load', return_value=mock_yaml_content):
            
            result = load_questions_dataset()
            assert len(result) == 2
            assert result[0]["question"] == "မေးခွန်း ၁"
    
    def test_search_in_dataset(self):
        """Test dataset search functionality"""
        # Mock dataset
        mock_dataset = [
            {"question": "ဥပဒေအရ ခိုးယူမှုအပြစ်ဒဏ်", "answer": "ခိုးယူမှုအတွက် အပြစ်မှာ..."},
            {"question": "ကားမတော်တဆမှု", "answer": "ကားမတော်တဆမှုအတွက်..."}
        ]
        
        # Patch the global dataset
        with patch('main.questions_dataset', mock_dataset):
            # Exact match
            result = search_in_dataset("ဥပဒေအရ ခိုးယူမှုအပြစ်ဒဏ်")
            assert result == "ခိုးယူမှုအတွက် အပြစ်မှာ..."
            
            # Partial match
            result = search_in_dataset("ခိုးယူမှု")
            assert result == "ခိုးယူမှုအတွက် အပြစ်မှာ..."
            
            # No match
            result = search_in_dataset("မတွေ့သောမေးခွန်း")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_query_gemini_ai_success(self):
        """Test successful Gemini AI query"""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "AI မှအဖြေ"
        mock_model.generate_content.return_value = mock_response
        
        with patch('main.gemini_model', mock_model):
            result = await query_gemini_ai("မေးခွန်း")
            assert result == "AI မှအဖြေ"
    
    @pytest.mark.asyncio
    async def test_query_gemini_ai_timeout(self):
        """Test Gemini AI timeout handling"""
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = asyncio.TimeoutError()
        
        with patch('main.gemini_model', mock_model):
            result = await query_gemini_ai("မေးခွန်း", timeout=1)
            assert result is None
    
    @pytest.mark.asyncio  
    async def test_query_gemini_ai_no_model(self):
        """Test Gemini AI when model is not initialized"""
        with patch('main.gemini_model', None):
            result = await query_gemini_ai("မေးခွန်း")
            assert result is None

# Test error handling
class TestErrorHandling:
    
    def test_invalid_json(self):
        """Test invalid JSON handling"""
        response = client.post("/ask", data="invalid json")
        assert response.status_code == 422
    
    def test_unsupported_method(self):
        """Test unsupported HTTP methods"""
        response = client.put("/ask")
        assert response.status_code == 405  # Method Not Allowed
        
        response = client.delete("/health")
        assert response.status_code == 405
    
    def test_nonexistent_endpoint(self):
        """Test accessing non-existent endpoints"""
        response = client.get("/nonexistent")
        assert response.status_code == 404

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
