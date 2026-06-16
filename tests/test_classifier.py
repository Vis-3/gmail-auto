import json
import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from llm_classifier import (
    Categories,
    ClassificationOutput,
    rule_based_filter,
    classify,
)


# ---------------------------------------------------------------------------
# ClassificationOutput schema
# ---------------------------------------------------------------------------

class TestClassificationOutput:
    def test_valid(self):
        out = ClassificationOutput(category="noise", confidence=0.9, rationale="test")
        assert out.category == Categories.noise

    def test_confidence_below_zero_fails(self):
        with pytest.raises(ValidationError):
            ClassificationOutput(category="noise", confidence=-0.1, rationale="test")

    def test_confidence_above_one_fails(self):
        with pytest.raises(ValidationError):
            ClassificationOutput(category="noise", confidence=1.1, rationale="test")

    def test_invalid_category_fails(self):
        with pytest.raises(ValidationError):
            ClassificationOutput(category="spam", confidence=0.5, rationale="test")

    def test_all_categories_accepted(self):
        for cat in ["job_update", "university", "conversation", "informational", "noise"]:
            out = ClassificationOutput(category=cat, confidence=0.5, rationale="test")
            assert out.category.value == cat


# ---------------------------------------------------------------------------
# rule_based_filter
# ---------------------------------------------------------------------------

class TestRuleBasedFilter:
    def _email(self, sender):
        return {"sender_email": sender, "subject": "Test", "body": "Test body"}

    def test_sender_in_sent_emails_is_conversation(self):
        email = self._email("friend@gmail.com")
        result = rule_based_filter(email, {"friend@gmail.com"})
        assert result == Categories.conversation

    def test_iu_edu_is_university(self):
        email = self._email("professor@iu.edu")
        result = rule_based_filter(email, set())
        assert result == Categories.university

    def test_known_noise_domain_is_noise(self):
        email = self._email("digest@tldr.tech")
        result = rule_based_filter(email, set())
        assert result == Categories.noise

    def test_another_noise_domain(self):
        email = self._email("jobs@wellfound.com")
        result = rule_based_filter(email, set())
        assert result == Categories.noise

    def test_unknown_sender_returns_none(self):
        email = self._email("someone@unknown.com")
        result = rule_based_filter(email, set())
        assert result is None

    def test_sent_email_takes_priority_over_iu(self):
        # If a known sender also has @iu.edu, conversation wins (checked first)
        email = self._email("ta@iu.edu")
        result = rule_based_filter(email, {"ta@iu.edu"})
        assert result == Categories.conversation

    def test_empty_sent_emails(self):
        email = self._email("anyone@gmail.com")
        result = rule_based_filter(email, set())
        assert result is None

    def test_missing_sender_email_key(self):
        result = rule_based_filter({}, set())
        assert result is None


# ---------------------------------------------------------------------------
# classify — rule path and LLM path
# ---------------------------------------------------------------------------

class TestClassify:
    def _email(self, sender):
        return {"sender_email": sender, "subject": "Hi", "body": "Hello"}

    def test_rule_match_skips_llm(self):
        email = self._email("prof@iu.edu")
        with patch("llm_classifier.classify_email") as mock_llm:
            result = classify(email, set())
        mock_llm.assert_not_called()
        assert result.category == Categories.university
        assert result.confidence == 1.0

    def test_no_rule_match_calls_llm(self):
        email = self._email("stranger@example.com")
        expected = ClassificationOutput(
            category="informational", confidence=0.8, rationale="Cold outreach."
        )
        with patch("llm_classifier.classify_email", return_value=expected) as mock_llm:
            result = classify(email, set())
        mock_llm.assert_called_once_with(email)
        assert result.category == Categories.informational

    def test_llm_response_parsed_correctly(self):
        email = self._email("recruiter@startup.com")
        llm_json = json.dumps({
            "category": "job_update",
            "confidence": 0.93,
            "rationale": "Recruiter email about a specific role."
        })
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = llm_json

        with patch("llm_classifier.client") as mock_client:
            mock_client.chat.completions.create.return_value = mock_completion
            result = classify(email, set())

        assert result.category == Categories.job_update
        assert result.confidence == pytest.approx(0.93)
