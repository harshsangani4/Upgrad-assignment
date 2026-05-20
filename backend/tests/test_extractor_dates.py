import datetime
import json
from unittest.mock import patch, MagicMock
import pytest

from backend.chat.extractor import extract_slots

@pytest.mark.parametrize(
    "msg, mock_date, expected_years",
    [
        ("I am working from January 2026", datetime.date(2026, 5, 20), 0),
        ("Since June 2023", datetime.date(2026, 5, 20), 2),
        ("for 5 years", datetime.date(2026, 5, 20), 5),
        ("going on 8 years", datetime.date(2026, 5, 20), 8),
        ("Just started last month", datetime.date(2026, 5, 20), 0),
        ("I started my career in 2018", datetime.date(2026, 5, 20), 8),
    ],
)
def test_extractor_dates(msg, mock_date, expected_years):
    with patch("backend.chat.extractor.date") as mock_date_module, \
         patch("backend.chat.extractor.OpenAI") as mock_openai:
        
        mock_date_module.today.return_value = mock_date
        mock_date_module.isoformat = datetime.date.isoformat
        
        # Mock the OpenAI client response
        mock_client_instance = MagicMock()
        mock_openai.return_value = mock_client_instance
        
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({"years_experience": expected_years})))
        ]
        mock_client_instance.chat.completions.create.return_value = mock_response
        
        updates = extract_slots([], msg)
        assert updates.get("years_experience") == expected_years
