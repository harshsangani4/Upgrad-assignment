import json
from typing import AsyncIterator, Iterator
from unittest.mock import patch, MagicMock

import pytest
from fastapi.responses import StreamingResponse

from backend.main import chat
from backend.schemas import ChatRequest
from backend.store import get_or_create_session

def test_chat_handler_single_emission():
    req = ChatRequest(session_id="single-emission-test", message="I want to learn AI")
    
    with patch("backend.main._generate_assistant") as mock_generate, \
         patch("backend.main.voice_lint") as mock_lint, \
         patch("backend.main.extract_slots") as mock_ext, \
         patch("backend.main.classify_intent") as mock_intent, \
         patch("backend.main._openai") as mock_openai:
         
        mock_intent.return_value = {"intent": "answering"}
        mock_ext.return_value = {"years_experience": 2}
        
        # Scenario: first draft fails lint, retry succeeds
        mock_generate.side_effect = [
            "This is the bad draft with Pattern A.",
            "This is the good draft."
        ]
        mock_lint.side_effect = [
            ["PATTERN_A"], # fails first time
            []             # passes second time
        ]
        
        response = chat(req)
        assert isinstance(response, StreamingResponse)
        
        import asyncio
        async def consume():
            res = []
            async for chunk in response.body_iterator:
                res.append(chunk.decode("utf-8"))
            return res
            
        chunks = asyncio.run(consume())
        full_output = "".join(chunks)
        
        # Parse SSE tokens to reconstruct the text
        reconstructed = []
        for line in full_output.splitlines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "value" in data:
                        reconstructed.append(data["value"])
                except json.JSONDecodeError:
                    pass
        
        final_text = "".join(reconstructed)
        
        assert "This is the good draft." in final_text
        assert "This is the bad draft" not in final_text

        # Verify exactly two calls were made to _generate_assistant (draft + retry)
        assert mock_generate.call_count == 2
