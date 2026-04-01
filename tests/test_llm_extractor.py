import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ceres.extractors.llm import ClaudeLLMExtractor, LLMExtractor

class TestClaudeLLMExtractor:
    @pytest.mark.asyncio
    async def test_extract_loan_data_calls_claude(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "programs": [{"program_name": "KPR BCA", "loan_type": "KPR", "min_interest_rate": 3.5, "max_interest_rate": 7.0}]
        }))]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        extractor = ClaudeLLMExtractor(client=mock_client)
        result = await extractor.extract_loan_data(html="<div>KPR BCA bunga 3.5%-7.0%</div>", bank_name="BCA")
        assert len(result["programs"]) == 1
        assert result["programs"][0]["program_name"] == "KPR BCA"

    @pytest.mark.asyncio
    async def test_extract_handles_malformed_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="not valid json")]
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        extractor = ClaudeLLMExtractor(client=mock_client)
        result = await extractor.extract_loan_data(html="<div>some html</div>", bank_name="BCA")
        assert result == {"programs": [], "error": "Failed to parse LLM response"}

    def test_implements_interface(self):
        mock_client = MagicMock()
        assert isinstance(ClaudeLLMExtractor(client=mock_client), LLMExtractor)
