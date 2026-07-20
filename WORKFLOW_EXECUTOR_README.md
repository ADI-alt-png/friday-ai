# Workflow Executor Documentation

## Overview

The `workflow_executor.py` module enables Friday AI to execute complex, multi-step automation chains with conditional logic, state management, and error handling.

## Features

### 1. Workflow Definition System
- **Sequential execution** of steps with pass-through context
- **YAML/JSON workflow definitions** for easy configuration
- **Step metadata**: action type, parameters, conditions, timeouts
- **Error handling strategies** per step (retry, fallback, continue)

### 2. Step Execution Engine
- **Atomic step execution** with timeout support
- **Conditional execution** - skip steps based on device state or previous results
- **Retry logic** with exponential backoff
- **Fallback steps** for error recovery
- **Context passing** - output from one step becomes input for next

### 3. Conditional Logic
- **Multiple condition types**:
  - `equals` / `not_equals` - Compare values
  - `greater_than` / `less_than` - Numeric comparison
  - `contains` - String matching
  - `has_value` - Check if variable exists
  - `battery_low`, `screen_on`, `app_running` - Device state
  - `custom` - Custom condition functions

- **Context references**: Use `$variable` to reference step outputs or context variables
- **Condition chains**: Multiple conditions with AND logic (all must pass)

### 4. Context Management
- **Persistent state** across workflow steps
- **Step results tracking** - access any step's output
- **Thread-safe operations** for concurrent workflows
- **Variable resolution** in parameters using `$variable` syntax

### 5. Pre-built Example Workflows

#### WhatsApp Workflow
```
open_whatsapp → search_contact → send_message
```
Demonstrates: app control, context passing, messaging

#### Screenshot & Analyze Workflow
```
take_screenshot → read_text (OCR) → save_result
```
Demonstrates: device control, OCR, result chaining

#### Reminder Workflow
```
check_time → [if hour matches] → open_app → set_reminder
```
Demonstrates: conditional execution, time-based triggers

## Usage

### Basic Workflow Execution

```python
from workflow_executor import WorkflowExecutor, ExampleWorkflows

# Create executor
executor = WorkflowExecutor(device_id="device123")

# Load example workflow
workflow = ExampleWorkflows.send_whatsapp_to_contact()

# Set initial context
initial_context = {
    "contact_name": "John",
    "contact_phone": "+1234567890",
    "message_text": "Hello!",
}

# Execute
success, context, results = executor.execute_workflow(workflow, initial_context)

# Check results
for result in results:
    print(f"{result.step_id}: {result.status.value}")
    if result.output:
        print(f"  Output: {result.output}")
```

### Creating Custom Workflows

```python
from workflow_executor import (
    WorkflowDefinition, WorkflowStep, Condition, 
    ErrorHandler, ConditionType
)

# Define steps
steps = [
    WorkflowStep(
        id="open_app",
        action_type="open_app",
        parameters={"package": "com.example.app"},
    ),
    WorkflowStep(
        id="send_message",
        action_type="send_whatsapp",
        parameters={
            "phone": "$contact_phone",
            "message": "$message_text",
        },
        conditions=[
            Condition(
                condition_type="equals",
                left_operand="$open_app.status",
                right_operand="opened",
            )
        ],
        error_handler=ErrorHandler(
            retry_count=2,
            on_failure="continue",
        ),
    ),
]

# Create workflow
workflow = WorkflowDefinition(
    id="my_workflow",
    name="My Custom Workflow",
    description="My custom workflow",
    steps=steps,
)

# Execute
executor = WorkflowExecutor()
success, context, results = executor.execute_workflow(workflow)
```

### Loading Workflows from JSON

```json
{
  "id": "my_workflow",
  "name": "My Workflow",
  "description": "Example workflow from JSON",
  "version": "1.0",
  "steps": [
    {
      "id": "step1",
      "action": "delay",
      "params": {"seconds": 2},
      "timeout": 30.0,
      "parallel_safe": false
    },
    {
      "id": "step2",
      "action": "send_whatsapp",
      "params": {
        "phone": "$phone_number",
        "message": "$message"
      },
      "conditions": [
        {
          "type": "has_value",
          "left": "$phone_number"
        }
      ],
      "error_handler": {
        "retry_count": 2,
        "retry_delay": 1.0,
        "on_failure": "continue"
      },
      "timeout": 30.0
    }
  ]
}
```

```python
executor = WorkflowExecutor()
workflow = executor.load_workflow_from_json("workflow.json")
success, context, results = executor.execute_workflow(workflow)
```

## Supported Actions

### Messaging
- `send_whatsapp` - Send WhatsApp message
- `send_sms` - Send SMS message

### App Control
- `open_app` - Open an application
- `close_app` - Close an application

### Device Control
- `take_screenshot` - Capture device screen
- `delay` - Wait for duration

### Information
- `check_battery` - Get battery level
- `check_time` - Get current time
- `read_text` - OCR on image

### Contact Management
- `search_contact` - Search address book

### Reminders
- `set_reminder` - Create a reminder

## Error Handling

Each step has an `ErrorHandler` with:
- `retry_count`: Number of retry attempts (default: 0)
- `retry_delay`: Seconds between retries (default: 1.0)
- `on_failure`: Action on failure
  - `"stop"`: Stop workflow (default)
  - `"continue"`: Skip and continue
  - `"execute_fallback"`: Run fallback step

### Example: Retry Logic

```python
step = WorkflowStep(
    id="send_message",
    action_type="send_whatsapp",
    parameters={"phone": "+1234567890", "message": "Hi"},
    error_handler=ErrorHandler(
        retry_count=3,          # Try 4 times total
        retry_delay=2.0,        # Wait 2 seconds between attempts
        on_failure="continue",  # Continue on failure
    ),
)
```

## Context Resolution

Parameters support context variable references using `$` prefix:

```python
# In context: contact_name = "John"
parameters = {
    "name": "$contact_name",  # Resolves to "John"
    "literal": "fixed_value",  # Keeps literal value
}
```

Context variables come from:
1. Initial context passed to workflow
2. Output from previous steps (e.g., `$step_id.output`)
3. Variables set via `context.set(key, value)`

## Workflow Execution Flow

```
1. Initialize WorkflowContext
2. For each step:
   a. Check conditions
   b. If conditions pass:
      - Execute with retry logic
      - Store result
   c. If conditions fail:
      - Mark as SKIPPED
   d. Handle errors:
      - Retry if configured
      - Execute fallback if configured
      - Stop or continue based on strategy
3. Return success status, context, and all results
```

## Performance Considerations

### Timeouts
- Each step has `timeout_seconds` (default: 30)
- Actions exceeding timeout will fail

### Parallel Execution (Future)
- Steps marked with `parallel_safe=True` can potentially run in parallel
- Currently all steps execute sequentially for safety

### Context Size
- Workflow context is thread-safe but stored in memory
- Large workflows with many results may consume memory
- Results are retained for full workflow execution

## Logging

Enable debug logging to trace workflow execution:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
# Now see detailed workflow execution logs
```

## Constraints & Limitations

1. **No parallel execution yet** - All steps run sequentially
2. **No persistence** - Workflows not saved to disk between runs
3. **Limited OCR** - Requires pytesseract (optional dependency)
4. **Device connection required** - Most actions need Android device via ADB
5. **No visual automation** - Can't record/replay UI interactions

## Future Enhancements

- [ ] Parallel step execution with dependency graphs
- [ ] Workflow persistence and resume capabilities
- [ ] Web UI for workflow builder
- [ ] Advanced condition expressions
- [ ] Loop and iteration support
- [ ] Workflow chaining and composition
- [ ] Performance metrics and profiling
- [ ] Integration with Friday's NLP for dynamic workflows
