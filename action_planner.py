"""
Action Planner - Parses user requests and determines action routing
Converts natural language requests into structured action plans with confidence scoring,
parameter extraction, and safety validation.
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum


class ActionType(Enum):
    """Supported action types"""
    SEND_SMS = "send_sms"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_TELEGRAM = "send_telegram"
    OPEN_APP = "open_app"
    CLOSE_APP = "close_app"
    GET_INFO = "get_info"
    SEARCH = "search"
    TASK_MANAGEMENT = "task_management"
    SCREENSHOT = "screenshot"
    INFORMATION = "information"


class ActionCategory(Enum):
    """Action categories for better organization"""
    MESSAGING = "messaging"
    APP_CONTROL = "app_control"
    INFORMATION = "information"
    SEARCH = "search"
    TASK = "task"
    DEVICE = "device"


@dataclass
class ActionResult:
    """Structured action parsing result"""
    is_action: bool
    action_type: Optional[str] = None
    confidence: float = 0.0
    parameters: Optional[Dict[str, Any]] = None
    explanation: str = ""
    clarification: Optional[str] = None
    category: Optional[str] = None
    requires_validation: bool = False


class ActionPlanner:
    """Parses natural language and routes to appropriate actions"""

    # Confidence threshold for action execution
    CONFIDENCE_THRESHOLD = 0.80

    # Action keywords mapping
    ACTION_KEYWORDS = {
        "send_sms": {
            "keywords": ["sms", "text message", "text"],
            "patterns": [
                r"send\s+(?:sms|text(?:\s+message)?)\s+to\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
                r"(?:sms|text)\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
                r"send\s+a\s+(?:sms|text(?:\s+message)?)\s+to\s+(\S+)(?:.*?)\"(.+?)\"",
                r"send\s+(?:sms|text(?:\s+message)?)\s+to\s+(\S+)$",  # Without message
            ],
        },
        "send_whatsapp": {
            "keywords": ["whatsapp", "whats app", "wa"],
            "patterns": [
                r"whatsapp\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
                r"send\s+(?:on\s+)?whatsapp\s+to\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
                r"send\s+whatsapp\s+(?:to\s+)?(\S+)(?:.*?)\"(.+?)\"",
            ],
        },
        "send_telegram": {
            "keywords": ["telegram"],
            "patterns": [
                r"telegram\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
                r"send\s+(?:on\s+)?telegram\s+to\s+(\S+)\s+(?:saying|message|with)\s+(.*)",
            ],
        },
        "open_app": {
            "keywords": ["open", "launch", "start"],
            "patterns": [
                r"(?:open|launch|start)\s+(?:the\s+)?([a-zA-Z0-9\s]+?)(?:\s+app)?$",
                r"open\s+([a-zA-Z0-9\s]+?)\s+on\s+phone",
                r"(?:open|launch|start)\s+(?:the\s+)?app",
            ],
        },
        "close_app": {
            "keywords": ["close", "quit", "exit"],
            "patterns": [
                r"(?:close|quit|exit)\s+(?:the\s+)?([a-zA-Z0-9\s]+?)(?:\s+app)?$",
                r"close\s+([a-zA-Z0-9\s]+?)\s+on\s+phone",
            ],
        },
        "screenshot": {
            "keywords": ["screenshot", "screen shot", "capture", "take picture"],
            "patterns": [
                r"(?:take\s+a\s+)?(?:screenshot|screen\s+shot|capture\s+screen)",
                r"take\s+a\s+picture\s+(?:of\s+)?(?:the\s+)?screen",
            ],
        },
    }

    # Common app name mappings
    APP_ALIASES = {
        "whatsapp": ["whatsapp", "wa", "whats app"],
        "telegram": ["telegram", "tg"],
        "instagram": ["instagram", "insta"],
        "facebook": ["facebook", "fb"],
        "twitter": ["twitter", "x"],
        "tiktok": ["tiktok", "tik tok"],
        "youtube": ["youtube", "yt"],
        "gmail": ["gmail", "email"],
        "maps": ["google maps", "maps"],
        "chrome": ["chrome", "google chrome"],
        "settings": ["settings", "preferences"],
    }

    # Blocked actions for safety
    BLOCKED_ACTIONS = {
        "factory_reset",
        "wipe_device",
        "uninstall_system_app",
        "change_permissions",
    }

    # Phone number patterns (supports multiple formats)
    PHONE_PATTERNS = [
        r"(\+?1?\d{9,15})",  # International format
        r"(\d{10})",  # 10-digit
        r"(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})",  # Formatted
    ]

    def __init__(self):
        """Initialize the action planner"""
        self.action_cache = {}

    def parse(self, user_input: str) -> ActionResult:
        """
        Parse user input and return structured action result

        Args:
            user_input: Natural language user request

        Returns:
            ActionResult with parsed action, confidence, and parameters
        """
        if not user_input or not isinstance(user_input, str):
            return ActionResult(
                is_action=False,
                confidence=0.0,
                explanation="Invalid or empty input",
            )

        user_input = user_input.strip().lower()

        # Try to match against known action patterns
        for action_type, config in self.ACTION_KEYWORDS.items():
            result = self._try_match_action(user_input, action_type, config)
            if result:
                return result

        # If no clear action matched, try information/search intent
        return self._handle_information_request(user_input)

    def _try_match_action(
        self, user_input: str, action_type: str, config: Dict
    ) -> Optional[ActionResult]:
        """Try to match user input against action patterns"""
        patterns = config.get("patterns", [])
        keywords = config.get("keywords", [])

        # Check if any keyword is present
        has_keyword = any(kw in user_input for kw in keywords)
        if not has_keyword:
            return None

        # Try to extract parameters using patterns
        for pattern in patterns:
            match = re.search(pattern, user_input)
            if match:
                groups = match.groups()

                # Extract parameters based on action type
                if action_type == "send_sms":
                    phone = groups[0] if len(groups) > 0 else None
                    message = groups[1] if len(groups) > 1 else None
                    return self._build_sms_action(phone, message)

                elif action_type == "send_whatsapp":
                    phone = groups[0] if len(groups) > 0 else None
                    message = groups[1] if len(groups) > 1 else None
                    return self._build_whatsapp_action(phone, message)

                elif action_type == "send_telegram":
                    contact = groups[0] if len(groups) > 0 else None
                    message = groups[1] if len(groups) > 1 else None
                    return self._build_telegram_action(contact, message)

                elif action_type == "open_app":
                    app_name = groups[0] if len(groups) > 0 else None
                    # Check for the special case of just "open app" with no name
                    if not app_name:
                        return self._build_open_app_action(None)
                    return self._build_open_app_action(app_name)

                elif action_type == "close_app":
                    app_name = groups[0] if len(groups) > 0 else None
                    return self._build_close_app_action(app_name)

                elif action_type == "screenshot":
                    return self._build_screenshot_action()

        return None

    def _build_sms_action(self, phone: str, message: str) -> ActionResult:
        """Build and validate SMS action"""
        if not phone or not message:
            clarification = "Please provide both phone number and message. Example: 'Send SMS to 9999999999 saying Hello'"
            if phone and not message:
                clarification = f"I found the number '{phone}' but need a message. What should I send?"
            return ActionResult(
                is_action=True,
                action_type=ActionType.SEND_SMS.value,
                confidence=0.3,
                explanation="SMS intent detected but missing parameters",
                clarification=clarification,
            )

        phone_valid, phone_clean = self._validate_phone_number(phone)
        if not phone_valid:
            return ActionResult(
                is_action=True,
                action_type=ActionType.SEND_SMS.value,
                confidence=0.4,
                explanation="SMS detected but invalid phone number",
                clarification=f"'{phone}' doesn't look like a valid phone number. Please provide a phone number.",
            )

        confidence = 0.95 if phone_clean and message else 0.80
        return ActionResult(
            is_action=True,
            action_type=ActionType.SEND_SMS.value,
            confidence=confidence,
            parameters={"phone": phone_clean, "message": message},
            explanation="Clear SMS send request",
            category=ActionCategory.MESSAGING.value,
            requires_validation=True,
        )

    def _build_whatsapp_action(self, phone: str, message: str) -> ActionResult:
        """Build and validate WhatsApp action"""
        if not phone or not message:
            return ActionResult(
                is_action=True,
                action_type=ActionType.SEND_WHATSAPP.value,
                confidence=0.3,
                explanation="WhatsApp intent detected but missing parameters",
                clarification="Please provide both phone number and message. Example: 'WhatsApp 9999999999 saying Hello'",
            )

        phone_valid, phone_clean = self._validate_phone_number(phone)
        if not phone_valid:
            return ActionResult(
                is_action=True,
                action_type=ActionType.SEND_WHATSAPP.value,
                confidence=0.4,
                explanation="WhatsApp detected but invalid phone number",
                clarification=f"'{phone}' doesn't look like a valid phone number.",
            )

        confidence = 0.95 if phone_clean and message else 0.80
        return ActionResult(
            is_action=True,
            action_type=ActionType.SEND_WHATSAPP.value,
            confidence=confidence,
            parameters={"phone": phone_clean, "message": message},
            explanation="Clear WhatsApp send request",
            category=ActionCategory.MESSAGING.value,
            requires_validation=True,
        )

    def _build_telegram_action(self, contact: str, message: str) -> ActionResult:
        """Build and validate Telegram action"""
        if not contact or not message:
            return ActionResult(
                is_action=True,
                action_type=ActionType.SEND_TELEGRAM.value,
                confidence=0.3,
                explanation="Telegram intent detected but missing parameters",
                clarification="Please provide contact and message. Example: 'Telegram john saying Hello'",
            )

        confidence = 0.85 if contact and message else 0.60
        return ActionResult(
            is_action=True,
            action_type=ActionType.SEND_TELEGRAM.value,
            confidence=confidence,
            parameters={"contact": contact.strip(), "message": message.strip()},
            explanation="Clear Telegram send request",
            category=ActionCategory.MESSAGING.value,
            requires_validation=True,
        )

    def _build_open_app_action(self, app_name: str) -> ActionResult:
        """Build and validate app opening action"""
        if not app_name or app_name.strip().lower() in ("app", "the app"):
            return ActionResult(
                is_action=True,
                action_type=ActionType.OPEN_APP.value,
                confidence=0.2,
                explanation="Open app intent detected but app not specified",
                clarification="Which app would you like to open?",
            )

        app_name = app_name.strip()
        package_name = self._resolve_app_package(app_name)

        if not package_name:
            confidence = 0.50
            clarification = f"Uncertain about app '{app_name}'. Did you mean one of: Instagram, Facebook, Chrome, Gmail?"
        else:
            confidence = 0.95

        return ActionResult(
            is_action=True,
            action_type=ActionType.OPEN_APP.value,
            confidence=confidence,
            parameters={
                "app_name": app_name,
                "package_name": package_name,
            },
            explanation=f"Open app request: {app_name}",
            clarification=clarification if not package_name else None,
            category=ActionCategory.APP_CONTROL.value,
            requires_validation=True,
        )

    def _build_close_app_action(self, app_name: str) -> ActionResult:
        """Build and validate app closing action"""
        if not app_name:
            return ActionResult(
                is_action=True,
                action_type=ActionType.CLOSE_APP.value,
                confidence=0.2,
                explanation="Close app intent detected but app not specified",
                clarification="Which app would you like to close?",
            )

        app_name = app_name.strip()
        package_name = self._resolve_app_package(app_name)

        if not package_name:
            confidence = 0.50
            clarification = f"Uncertain about app '{app_name}'. Did you mean one of: Instagram, Facebook, Chrome, Gmail?"
        else:
            confidence = 0.95

        return ActionResult(
            is_action=True,
            action_type=ActionType.CLOSE_APP.value,
            confidence=confidence,
            parameters={
                "app_name": app_name,
                "package_name": package_name,
            },
            explanation=f"Close app request: {app_name}",
            clarification=clarification if not package_name else None,
            category=ActionCategory.APP_CONTROL.value,
            requires_validation=True,
        )

    def _build_screenshot_action(self) -> ActionResult:
        """Build screenshot action"""
        return ActionResult(
            is_action=True,
            action_type=ActionType.SCREENSHOT.value,
            confidence=0.98,
            parameters={},
            explanation="Screenshot request",
            category=ActionCategory.DEVICE.value,
            requires_validation=False,
        )

    def _handle_information_request(self, user_input: str) -> ActionResult:
        """Handle information/search requests"""
        # Detect search intent (but be more specific to avoid false positives)
        search_keywords = ["search ", "find ", "look up "]
        is_search = any(kw in user_input for kw in search_keywords)

        if is_search:
            return ActionResult(
                is_action=False,
                action_type=ActionType.SEARCH.value,
                confidence=0.70,
                parameters={"query": user_input},
                explanation="Information search request",
                category=ActionCategory.SEARCH.value,
            )

        # Detect task/reminder intent
        task_keywords = ["remind", "note", "remember", "task", "todo", "set alarm"]
        is_task = any(kw in user_input for kw in task_keywords)

        if is_task:
            return ActionResult(
                is_action=False,
                action_type=ActionType.TASK_MANAGEMENT.value,
                confidence=0.75,
                parameters={"task": user_input},
                explanation="Task or reminder request",
                category=ActionCategory.TASK.value,
            )

        # Generic information request
        return ActionResult(
            is_action=False,
            confidence=0.60,
            action_type=ActionType.INFORMATION.value,
            parameters={"query": user_input},
            explanation="General information request",
            category=ActionCategory.INFORMATION.value,
        )

    def _validate_phone_number(self, phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate and clean phone number

        Returns:
            (is_valid, cleaned_phone_number)
        """
        if not phone:
            return (False, None)

        # Remove common formatting characters
        cleaned = re.sub(r"[\s\-().+]", "", phone)

        # Check if it's a valid number
        for pattern in self.PHONE_PATTERNS:
            if re.match(pattern, cleaned):
                return (True, cleaned)

        return (False, None)

    def _resolve_app_package(self, app_name: str) -> Optional[str]:
        """
        Resolve app name to package name

        Args:
            app_name: Human-readable app name

        Returns:
            Package name or None if not recognized
        """
        app_name = app_name.strip().lower()

        # Check direct aliases
        for package, aliases in self.APP_ALIASES.items():
            if any(alias in app_name or app_name in alias for alias in aliases):
                return package

        # If no match found
        return None

    def should_execute_action(self, result: ActionResult) -> bool:
        """
        Determine if action should be executed based on confidence threshold

        Args:
            result: ActionResult from parse()

        Returns:
            True if confidence exceeds threshold and action is safe
        """
        if not result.is_action:
            return False

        if result.confidence < self.CONFIDENCE_THRESHOLD:
            return False

        if result.action_type in self.BLOCKED_ACTIONS:
            return False

        return True

    def validate_action(self, result: ActionResult) -> Tuple[bool, str]:
        """
        Validate action parameters for safety

        Args:
            result: ActionResult to validate

        Returns:
            (is_valid, validation_message)
        """
        if not result.requires_validation:
            return (True, "No validation required")

        action_type = result.action_type
        params = result.parameters or {}

        # SMS validation
        if action_type == ActionType.SEND_SMS.value:
            if "phone" not in params or not params["phone"]:
                return (False, "Phone number is required for SMS")
            if "message" not in params or not params["message"]:
                return (False, "Message text is required for SMS")
            if len(params["message"]) > 160:
                return (False, "Message too long (max 160 characters for SMS)")
            return (True, "SMS parameters valid")

        # WhatsApp validation
        if action_type == ActionType.SEND_WHATSAPP.value:
            if "phone" not in params or not params["phone"]:
                return (False, "Phone number is required for WhatsApp")
            if "message" not in params or not params["message"]:
                return (False, "Message text is required for WhatsApp")
            return (True, "WhatsApp parameters valid")

        # Telegram validation
        if action_type == ActionType.SEND_TELEGRAM.value:
            if "contact" not in params or not params["contact"]:
                return (False, "Contact is required for Telegram")
            if "message" not in params or not params["message"]:
                return (False, "Message text is required for Telegram")
            return (True, "Telegram parameters valid")

        # App control validation
        if action_type in (ActionType.OPEN_APP.value, ActionType.CLOSE_APP.value):
            if "app_name" not in params or not params["app_name"]:
                return (False, "App name is required")
            return (True, f"App control parameters valid")

        return (True, "Validation passed")

    def format_result(self, result: ActionResult) -> Dict[str, Any]:
        """Convert ActionResult to dictionary for serialization"""
        return {
            "is_action": result.is_action,
            "action_type": result.action_type,
            "confidence": result.confidence,
            "parameters": result.parameters,
            "explanation": result.explanation,
            "clarification": result.clarification,
            "category": result.category,
            "requires_validation": result.requires_validation,
        }

    def parse_with_context(
        self, user_input: str, previous_context: Optional[Dict] = None
    ) -> ActionResult:
        """
        Parse user input with conversation context

        Useful for resolving ambiguous requests using previous context.

        Args:
            user_input: Current user request
            previous_context: Previous action context

        Returns:
            ActionResult with context-aware parsing
        """
        result = self.parse(user_input)

        # Try to use context for resolution if current parse is uncertain
        if (
            result.confidence < 0.70
            and previous_context
            and "recipient" in previous_context
        ):
            # If previous message was about a contact, use that context
            if "send_sms" in user_input.lower() or "sms" in user_input.lower():
                phone = previous_context.get("recipient", {}).get("phone")
                message = user_input.replace("send sms", "").replace("sms", "").strip()
                if phone and message:
                    result = self._build_sms_action(phone, message)
                    result.explanation += " (resolved using conversation context)"

        return result


# Convenience functions
def create_planner() -> ActionPlanner:
    """Factory function to create an ActionPlanner instance"""
    return ActionPlanner()


def parse_action(user_input: str) -> Dict[str, Any]:
    """Quick parse function without needing to instantiate"""
    planner = create_planner()
    result = planner.parse(user_input)
    return planner.format_result(result)
