import pytest
from unittest.mock import patch, MagicMock

from backend.main import chat
from backend.schemas import ChatRequest
from backend.store import get_or_create_session

def test_template_rotation_ack_then_ask():
    # Run 6 simulated ACK_THEN_ASK turns
    req = ChatRequest(session_id="rotation-test", message="hi")
    
    with patch("backend.main._generate_assistant") as mock_generate, \
         patch("backend.main.voice_lint") as mock_lint, \
         patch("backend.main.extract_slots") as mock_ext, \
         patch("backend.main.classify_intent") as mock_intent:
        
        mock_intent.return_value = {"intent": "answering"}
        mock_ext.return_value = {} # no slots filled, always prompts ACK_THEN_ASK
        mock_lint.return_value = []
        
        responses = []
        for i in range(6):
            # Mock the assistant output to uniquely identify this response
            mock_generate.return_value = f"Opener word {i} here then question?"
            response = chat(req)
            import asyncio
            async def consume():
                res = []
                async for chunk in response.body_iterator:
                    res.append(chunk.decode("utf-8"))
                return res
            chunks = asyncio.run(consume())
            responses.append(mock_generate.return_value)
            
        # Ensure state captured them
        state = get_or_create_session("rotation-test")
        assert len(state.messages) >= 6
        assert len(state.used_templates["ack_then_ask"]) > 0

def test_template_rotation_recommend():
    with patch("backend.main._generate_assistant") as mock_generate, \
         patch("backend.main.voice_lint") as mock_lint, \
         patch("backend.main.extract_slots") as mock_ext, \
         patch("backend.main._plan_turn") as mock_plan:
         
        mock_lint.return_value = []
        mock_ext.return_value = {}
        
        # We need _build_chat_messages to capture the template injected.
        # Instead of parsing the output, we can check the used_templates tracker
        state = get_or_create_session("rotation-test-2")
        mock_plan.return_value = {"hint": "READY_TO_RECOMMEND", "phrasing": None, "recommendations": [], "quick_slot": None}
        
        from backend.main import _directive_text
        
        # Call 4 times, ensure we get 3 unique indices then a reset + 1 new index
        indices = []
        for i in range(4):
            _directive_text("READY_TO_RECOMMEND", None, state)
            indices.append(state.used_templates["recommend_transition"][-1])
            
        assert len(set(indices[:3])) == 3 # First 3 should be unique
