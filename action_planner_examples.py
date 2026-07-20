"""
Example usage of the ActionPlanner module
Demonstrates all key features and integration patterns
"""

from action_planner import ActionPlanner, create_planner, parse_action

# ============================================================================
# BASIC USAGE
# ============================================================================

planner = ActionPlanner()

# Example 1: High-confidence SMS action
result = planner.parse("send SMS to 9999999999 saying hello there")
print("Example 1: High-confidence SMS")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Should execute: {planner.should_execute_action(result)}")
print()

# Example 2: Ambiguous contact (low confidence)
result = planner.parse("message john")
print("Example 2: Ambiguous contact")
print(f"  Is action: {result.is_action}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Explanation: {result.explanation}")
print()

# Example 3: Invalid phone number
result = planner.parse("send SMS to john saying hello")
print("Example 3: Invalid phone number")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Clarification: {result.clarification}")
print()

# Example 4: App opening with high confidence
result = planner.parse("open instagram")
print("Example 4: App opening (known app)")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Parameters: {result.parameters}")
print()

# Example 5: App opening with unknown app
result = planner.parse("open unknownapp999")
print("Example 5: App opening (unknown app)")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Clarification: {result.clarification}")
print()

# Example 6: WhatsApp action
result = planner.parse("whatsapp 9999999999 saying great news")
print("Example 6: WhatsApp action")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Should execute: {planner.should_execute_action(result)}")
print()

# Example 7: Information request (search)
result = planner.parse("search for python tutorials")
print("Example 7: Information request (search)")
print(f"  Is action: {result.is_action}")
print(f"  Action type: {result.action_type}")
print(f"  Query: {result.parameters.get('query')}")
print()

# Example 8: Screenshot action
result = planner.parse("take a screenshot")
print("Example 8: Screenshot action")
print(f"  Action: {result.action_type}")
print(f"  Confidence: {result.confidence:.0%}")
print(f"  Should execute: {planner.should_execute_action(result)}")
print()

# ============================================================================
# PARAMETER EXTRACTION
# ============================================================================

print("\n=== PARAMETER EXTRACTION ===\n")

# Extract phone and message
result = planner.parse("send SMS to 9876543210 saying Happy birthday")
if result.parameters:
    print(f"Phone: {result.parameters.get('phone')}")
    print(f"Message: {result.parameters.get('message')}")
print()

# ============================================================================
# VALIDATION
# ============================================================================

print("\n=== VALIDATION ===\n")

result = planner.parse("send SMS to 9999999999 saying hello")
is_valid, msg = planner.validate_action(result)
print(f"Validation: {is_valid} - {msg}")
print()

# Long message validation
result = planner.parse("send SMS to 9999999999 saying " + "x" * 200)
is_valid, msg = planner.validate_action(result)
print(f"Long message validation: {is_valid} - {msg}")
print()

# ============================================================================
# FORMATTING AND SERIALIZATION
# ============================================================================

print("\n=== FORMATTING ===\n")

result = planner.parse("open chrome")
formatted = planner.format_result(result)
print(f"Formatted result: {formatted}")
print()

# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

print("\n=== CONVENIENCE FUNCTIONS ===\n")

# Quick parse without creating planner instance
result_dict = parse_action("send SMS to 9999999999 saying hello")
print(f"Quick parse: {result_dict['is_action']} - {result_dict['action_type']}")
print()

# Create planner using factory
planner2 = create_planner()
print(f"Factory created planner: {type(planner2).__name__}")
print()

# ============================================================================
# CONTEXT-AWARE PARSING
# ============================================================================

print("\n=== CONTEXT-AWARE PARSING ===\n")

# First request establishes context
result1 = planner.parse("message 9999999999")
print(f"First request - confidence: {result1.confidence:.0%}")

# Second request uses context
context = {"recipient": {"phone": "9999999999"}}
result2 = planner.parse_with_context("send SMS", previous_context=context)
print(f"Second request with context - confidence: {result2.confidence:.0%}")
print()

# ============================================================================
# EDGE CASES
# ============================================================================

print("\n=== EDGE CASES ===\n")

# Mixed case
result = planner.parse("SEND SMS TO 9999999999 SAYING HELLO")
print(f"Mixed case handling: {result.action_type}")

# Extra whitespace
result = planner.parse("  send   SMS    to 9999999999 saying hello  ")
print(f"Whitespace handling: {result.action_type}")

# Special characters in message
result = planner.parse('send SMS to 9999999999 saying "hey! how are you? 😊"')
print(f"Special characters: {result.action_type}")

# Alternative phone formats
result = planner.parse("send SMS to 999-999-9999 saying test")
if result.parameters:
    print(f"Formatted phone handling: {result.parameters.get('phone')}")
print()

# ============================================================================
# INTEGRATION WITH ANDROID CONTROLLER
# ============================================================================

print("\n=== INTEGRATION EXAMPLE ===\n")

from android_controller import AndroidController, SAFE_ACTIONS

# Parse request
result = planner.parse("send SMS to 9999999999 saying hello from friday")

# Check if should execute
if planner.should_execute_action(result):
    # Validate parameters
    is_valid, validation_msg = planner.validate_action(result)
    if is_valid:
        # Can now pass to AndroidController
        print(f"Action ready for execution: {result.action_type}")
        print(f"Parameters: {result.parameters}")
        
        # Example: would call android_controller
        # controller = AndroidController()
        # success, msg = controller.send_sms(
        #     result.parameters['phone'],
        #     result.parameters['message']
        # )
else:
    print(f"Action not executable: {result.explanation}")
    if result.clarification:
        print(f"Clarification: {result.clarification}")
