"""
Tests for action_planner.py
Validates intent detection, confidence scoring, parameter extraction, and safety validation
"""

import unittest
from action_planner import (
    ActionPlanner,
    ActionResult,
    ActionType,
    ActionCategory,
    create_planner,
    parse_action,
)


class TestActionDetection(unittest.TestCase):
    """Test basic action detection and classification"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_sms_action_detection(self):
        """Test SMS action is correctly identified"""
        result = self.planner.parse("send SMS to 9999999999 saying hello there")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.SEND_SMS.value)
        self.assertGreater(result.confidence, 0.90)

    def test_whatsapp_action_detection(self):
        """Test WhatsApp action is correctly identified"""
        result = self.planner.parse("whatsapp john saying hello")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.SEND_WHATSAPP.value)

    def test_open_app_action_detection(self):
        """Test app opening action is detected"""
        result = self.planner.parse("open instagram")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.OPEN_APP.value)

    def test_close_app_action_detection(self):
        """Test app closing action is detected"""
        result = self.planner.parse("close facebook app")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.CLOSE_APP.value)

    def test_screenshot_action_detection(self):
        """Test screenshot action is detected"""
        result = self.planner.parse("take a screenshot")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.SCREENSHOT.value)
        self.assertGreater(result.confidence, 0.95)

    def test_information_request_detection(self):
        """Test information request falls through correctly"""
        result = self.planner.parse("what is the capital of france")
        self.assertFalse(result.is_action)
        self.assertEqual(result.action_type, ActionType.INFORMATION.value)

    def test_search_request_detection(self):
        """Test search request is detected"""
        result = self.planner.parse("search for python tutorial")
        self.assertFalse(result.is_action)
        self.assertEqual(result.action_type, ActionType.SEARCH.value)

    def test_task_request_detection(self):
        """Test task/reminder request is detected"""
        result = self.planner.parse("remind me to buy groceries")
        self.assertFalse(result.is_action)
        self.assertEqual(result.action_type, ActionType.TASK_MANAGEMENT.value)


class TestParameterExtraction(unittest.TestCase):
    """Test parameter extraction from natural language"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_extract_phone_number(self):
        """Test phone number extraction"""
        result = self.planner.parse("send SMS to 9999999999 saying hello")
        self.assertIsNotNone(result.parameters)
        self.assertIn("phone", result.parameters)
        self.assertEqual(result.parameters["phone"], "9999999999")

    def test_extract_message_text(self):
        """Test message text extraction"""
        result = self.planner.parse("send SMS to 9999999999 saying hello there")
        self.assertIn("message", result.parameters)
        self.assertEqual(result.parameters["message"], "hello there")

    def test_extract_app_name(self):
        """Test app name extraction"""
        result = self.planner.parse("open instagram")
        self.assertIn("app_name", result.parameters)
        self.assertEqual(result.parameters["app_name"], "instagram")

    def test_extract_query_for_search(self):
        """Test query extraction for searches"""
        result = self.planner.parse("search for machine learning courses")
        self.assertIn("query", result.parameters)
        self.assertIn("machine learning", result.parameters["query"])

    def test_handle_alternative_sms_format(self):
        """Test SMS with alternative phrasing"""
        result = self.planner.parse("text 9999999999 saying birthday greetings")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.SEND_SMS.value)
        self.assertIn("phone", result.parameters)
        self.assertIn("message", result.parameters)


class TestConfidenceScoring(unittest.TestCase):
    """Test confidence scoring and thresholds"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_high_confidence_clear_sms(self):
        """Test high confidence for clear SMS request"""
        result = self.planner.parse("send SMS to 9999999999 saying hello")
        self.assertGreater(result.confidence, 0.90)

    def test_high_confidence_screenshot(self):
        """Test high confidence for screenshot"""
        result = self.planner.parse("take a screenshot")
        self.assertGreater(result.confidence, 0.95)

    def test_low_confidence_ambiguous_contact(self):
        """Test low confidence for ambiguous contact"""
        result = self.planner.parse("message john")
        self.assertLess(result.confidence, self.planner.CONFIDENCE_THRESHOLD)

    def test_low_confidence_no_message(self):
        """Test low confidence when message is missing"""
        result = self.planner.parse("send SMS to 9999999999")
        self.assertLess(result.confidence, self.planner.CONFIDENCE_THRESHOLD)

    def test_medium_confidence_search(self):
        """Test medium confidence for search"""
        result = self.planner.parse("search for python")
        self.assertGreater(result.confidence, 0.60)
        self.assertLess(result.confidence, 0.90)

    def test_should_execute_action_threshold(self):
        """Test execution threshold logic"""
        # High confidence - should execute
        result = self.planner.parse("send SMS to 9999999999 saying hello")
        self.assertTrue(self.planner.should_execute_action(result))

        # Low confidence - should not execute
        result = self.planner.parse("message john")
        self.assertFalse(self.planner.should_execute_action(result))


class TestPhoneNumberValidation(unittest.TestCase):
    """Test phone number validation and cleaning"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_valid_10_digit_phone(self):
        """Test valid 10-digit phone number"""
        valid, cleaned = self.planner._validate_phone_number("9999999999")
        self.assertTrue(valid)
        self.assertEqual(cleaned, "9999999999")

    def test_valid_formatted_phone(self):
        """Test valid formatted phone number"""
        valid, cleaned = self.planner._validate_phone_number("999-999-9999")
        self.assertTrue(valid)
        self.assertIsNotNone(cleaned)

    def test_valid_international_format(self):
        """Test valid international phone format"""
        valid, cleaned = self.planner._validate_phone_number("+919999999999")
        self.assertTrue(valid)
        self.assertIsNotNone(cleaned)

    def test_invalid_phone_too_short(self):
        """Test invalid phone number (too short)"""
        valid, cleaned = self.planner._validate_phone_number("123")
        self.assertFalse(valid)

    def test_invalid_phone_letters(self):
        """Test invalid phone with letters"""
        valid, cleaned = self.planner._validate_phone_number("abc123def")
        self.assertFalse(valid)

    def test_empty_phone(self):
        """Test empty phone number"""
        valid, cleaned = self.planner._validate_phone_number("")
        self.assertFalse(valid)


class TestAppNameResolution(unittest.TestCase):
    """Test app name resolution and aliasing"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_resolve_whatsapp_alias(self):
        """Test WhatsApp alias resolution"""
        package = self.planner._resolve_app_package("whatsapp")
        self.assertEqual(package, "whatsapp")

    def test_resolve_wa_shorthand(self):
        """Test WA shorthand resolution"""
        package = self.planner._resolve_app_package("wa")
        self.assertEqual(package, "whatsapp")

    def test_resolve_instagram_alias(self):
        """Test Instagram alias resolution"""
        package = self.planner._resolve_app_package("insta")
        self.assertEqual(package, "instagram")

    def test_resolve_facebook_alias(self):
        """Test Facebook alias resolution"""
        package = self.planner._resolve_app_package("fb")
        self.assertEqual(package, "facebook")

    def test_unknown_app_returns_none(self):
        """Test unknown app returns None"""
        package = self.planner._resolve_app_package("unknownapp123")
        self.assertIsNone(package)


class TestSafetyValidation(unittest.TestCase):
    """Test safety validation and parameter checking"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_validate_sms_parameters(self):
        """Test SMS parameter validation"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.SEND_SMS.value,
            confidence=0.95,
            parameters={"phone": "9999999999", "message": "hello"},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertTrue(valid)

    def test_validate_sms_missing_phone(self):
        """Test SMS validation fails without phone"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.SEND_SMS.value,
            confidence=0.95,
            parameters={"message": "hello"},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertFalse(valid)

    def test_validate_sms_missing_message(self):
        """Test SMS validation fails without message"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.SEND_SMS.value,
            confidence=0.95,
            parameters={"phone": "9999999999"},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertFalse(valid)

    def test_validate_sms_message_too_long(self):
        """Test SMS validation fails for long message"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.SEND_SMS.value,
            confidence=0.95,
            parameters={"phone": "9999999999", "message": "x" * 200},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertFalse(valid)

    def test_validate_whatsapp_parameters(self):
        """Test WhatsApp parameter validation"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.SEND_WHATSAPP.value,
            confidence=0.95,
            parameters={"phone": "9999999999", "message": "hello"},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertTrue(valid)

    def test_validate_app_control_parameters(self):
        """Test app control parameter validation"""
        result = ActionResult(
            is_action=True,
            action_type=ActionType.OPEN_APP.value,
            confidence=0.95,
            parameters={"app_name": "instagram", "package_name": "instagram"},
            requires_validation=True,
        )
        valid, msg = self.planner.validate_action(result)
        self.assertTrue(valid)


class TestFallbackStrategy(unittest.TestCase):
    """Test fallback and clarification for ambiguous requests"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_clarification_ambiguous_contact(self):
        """Test clarification for ambiguous contact"""
        result = self.planner.parse("message john")
        # Should not be a high-confidence action since it lacks proper structure
        self.assertTrue(
            not result.is_action or result.confidence < self.planner.CONFIDENCE_THRESHOLD
        )

    def test_clarification_missing_phone(self):
        """Test clarification for missing phone"""
        result = self.planner.parse("send SMS to john")
        self.assertIsNotNone(result.clarification)

    def test_clarification_missing_app_name(self):
        """Test clarification for missing app name"""
        result = self.planner.parse("open app")
        # Should detect app opening intent but with low confidence
        self.assertEqual(result.action_type, ActionType.OPEN_APP.value)
        self.assertLess(result.confidence, self.planner.CONFIDENCE_THRESHOLD)
        self.assertIsNotNone(result.clarification)

    def test_fallback_to_information(self):
        """Test fallback to information for unclear requests"""
        result = self.planner.parse("what should i have for lunch")
        self.assertFalse(result.is_action)
        self.assertEqual(result.action_type, ActionType.INFORMATION.value)


class TestResultFormatting(unittest.TestCase):
    """Test result formatting and serialization"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_format_result_to_dict(self):
        """Test ActionResult formatting to dictionary"""
        result = self.planner.parse("send SMS to 9999999999 saying hello")
        formatted = self.planner.format_result(result)

        self.assertIsInstance(formatted, dict)
        self.assertIn("is_action", formatted)
        self.assertIn("action_type", formatted)
        self.assertIn("confidence", formatted)
        self.assertIn("parameters", formatted)

    def test_quick_parse_function(self):
        """Test quick parse convenience function"""
        result_dict = parse_action("send SMS to 9999999999 saying hello")
        self.assertIsInstance(result_dict, dict)
        self.assertTrue(result_dict["is_action"])

    def test_create_planner_factory(self):
        """Test factory function"""
        planner = create_planner()
        self.assertIsInstance(planner, ActionPlanner)


class TestContextAwareParsing(unittest.TestCase):
    """Test context-aware parsing"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_parse_with_no_context(self):
        """Test parsing without context"""
        result = self.planner.parse_with_context("send SMS saying hello")
        self.assertIsNotNone(result)

    def test_parse_with_previous_recipient_context(self):
        """Test parsing using previous recipient context"""
        context = {"recipient": {"phone": "9999999999"}}
        result = self.planner.parse_with_context("send SMS", previous_context=context)
        self.assertIsNotNone(result)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_empty_input(self):
        """Test empty input handling"""
        result = self.planner.parse("")
        self.assertFalse(result.is_action)
        self.assertEqual(result.confidence, 0.0)

    def test_none_input(self):
        """Test None input handling"""
        result = self.planner.parse(None)
        self.assertFalse(result.is_action)

    def test_mixed_case_input(self):
        """Test mixed case input"""
        result = self.planner.parse("SEND SMS to 9999999999 SAYING HELLO")
        self.assertTrue(result.is_action)
        self.assertEqual(result.action_type, ActionType.SEND_SMS.value)

    def test_extra_whitespace(self):
        """Test input with extra whitespace"""
        result = self.planner.parse("  send   SMS    to 9999999999 saying hello  ")
        self.assertTrue(result.is_action)

    def test_special_characters_in_message(self):
        """Test special characters in message"""
        result = self.planner.parse("send SMS to 9999999999 saying hey! how are you? 😊")
        self.assertTrue(result.is_action)
        self.assertIn("message", result.parameters)


class TestIntegration(unittest.TestCase):
    """Integration tests with multiple components"""

    def setUp(self):
        self.planner = ActionPlanner()

    def test_full_sms_flow(self):
        """Test complete SMS action flow"""
        result = self.planner.parse("send SMS to 9999999999 saying hello there")

        self.assertTrue(result.is_action)
        self.assertTrue(self.planner.should_execute_action(result))

        valid, msg = self.planner.validate_action(result)
        self.assertTrue(valid)

        formatted = self.planner.format_result(result)
        self.assertIsInstance(formatted, dict)

    def test_full_information_flow(self):
        """Test complete information request flow"""
        result = self.planner.parse("what is python")

        self.assertFalse(result.is_action or result.confidence >= self.planner.CONFIDENCE_THRESHOLD)
        self.assertFalse(self.planner.should_execute_action(result))

    def test_action_threshold_boundary(self):
        """Test action execution at confidence boundary"""
        # Parse ambiguous app - should be below threshold
        result = self.planner.parse("open unknownapp999")
        should_exec = self.planner.should_execute_action(result)
        # Uncertain apps should be below threshold
        self.assertLessEqual(result.confidence, self.planner.CONFIDENCE_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
