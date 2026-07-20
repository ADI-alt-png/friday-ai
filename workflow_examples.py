"""
Real-world workflow examples for Friday AI
Demonstrates practical use cases of the workflow executor
"""

import sys
sys.path.insert(0, '.')

from workflow_executor import (
    WorkflowExecutor, WorkflowDefinition, WorkflowStep, 
    Condition, ErrorHandler, ExampleWorkflows
)
import json


def example_1_basic_messaging():
    """Example 1: Send automated message to contact"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Send Message to Contact")
    print("="*60)
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    # Use pre-built workflow
    workflow = ExampleWorkflows.send_whatsapp_to_contact()
    
    # Set up context with contact details
    context = {
        "contact_name": "Alice Johnson",
        "contact_phone": "+1-555-0123",
        "message_text": "Hey Alice! Just checking in. How are you doing?",
    }
    
    print("\nWorkflow: Send WhatsApp to Contact")
    print("Context:")
    for key, value in context.items():
        print(f"  {key}: {value}")
    
    # Execute
    success, ctx, results = executor.execute_workflow(workflow, context)
    
    print("\nExecution Results:")
    for r in results:
        print(f"  {r.step_id}: {r.status.value}")


def example_2_screenshot_analysis():
    """Example 2: Take screenshot and analyze content"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Screenshot and Analyze")
    print("="*60)
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    workflow = ExampleWorkflows.screenshot_and_analyze()
    
    print("\nWorkflow: Screenshot and Analyze")
    print("Steps:")
    for step in workflow.steps:
        print(f"  - {step.id}: {step.action_type}")
    
    success, ctx, results = executor.execute_workflow(workflow)
    
    print("\nResults:")
    for r in results:
        if r.output:
            print(f"  {r.step_id}:")
            print(f"    Status: {r.output.get('status')}")
            if 'text' in r.output:
                print(f"    Text (OCR): {r.output['text'][:50]}...")


def example_3_reminder_automation():
    """Example 3: Time-based reminder automation"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Automated Reminder Based on Time")
    print("="*60)
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    workflow = ExampleWorkflows.reminder_workflow()
    
    context = {
        "reminder_title": "Team Standup Meeting",
        "reminder_time": "14:00",
    }
    
    print("\nWorkflow: Reminder Automation")
    print("Context:")
    for key, value in context.items():
        print(f"  {key}: {value}")
    
    print("\nWorkflow Steps with Conditions:")
    for step in workflow.steps:
        cond_str = f" [conditions: {len(step.conditions)}]" if step.conditions else " [no conditions]"
        print(f"  - {step.id}: {step.action_type}{cond_str}")
    
    success, ctx, results = executor.execute_workflow(workflow, context)
    
    print("\nExecution Flow:")
    for r in results:
        status_icon = ">" if r.status.value == "success" else "-" if r.status.value == "skipped" else "X"
        print(f"  [{status_icon}] {r.step_id}: {r.status.value}")


def example_4_custom_workflow():
    """Example 4: Create and execute custom workflow"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Custom Workflow - Morning Routine")
    print("="*60)
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    # Define custom workflow
    steps = [
        WorkflowStep(
            id="check_time",
            action_type="check_time",
            parameters={},
        ),
        WorkflowStep(
            id="check_battery",
            action_type="check_battery",
            parameters={},
        ),
        WorkflowStep(
            id="open_news_app",
            action_type="open_app",
            parameters={
                "package": "com.google.android.apps.mediashell",
                "name": "Google News",
            },
            conditions=[
                Condition(
                    condition_type="has_value",
                    left_operand="$check_time.output",
                )
            ],
        ),
        WorkflowStep(
            id="wait",
            action_type="delay",
            parameters={"seconds": 2},
        ),
        WorkflowStep(
            id="open_calendar",
            action_type="open_app",
            parameters={
                "package": "com.google.android.calendar",
                "name": "Calendar",
            },
            error_handler=ErrorHandler(
                retry_count=1,
                on_failure="continue",
            ),
        ),
    ]
    
    workflow = WorkflowDefinition(
        id="morning_routine",
        name="Morning Routine Automation",
        description="Check status and open news/calendar apps",
        steps=steps,
        tags=["routine", "automation", "morning"],
    )
    
    print("\nCustom Workflow: Morning Routine")
    print(f"  Description: {workflow.description}")
    print(f"  Steps: {len(workflow.steps)}")
    
    success, ctx, results = executor.execute_workflow(workflow)
    
    print("\nWorkflow Execution Summary:")
    print(f"  Total steps: {len(results)}")
    print(f"  Successful: {sum(1 for r in results if r.status.value == 'success')}")
    print(f"  Skipped: {sum(1 for r in results if r.status.value == 'skipped')}")
    print(f"  Failed: {sum(1 for r in results if r.status.value == 'failed')}")
    print(f"  Overall success: {success}")


def example_5_emergency_workflow():
    """Example 5: Emergency alert workflow"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Emergency Alert - Multi-Channel")
    print("="*60)
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    # Create emergency workflow
    steps = [
        WorkflowStep(
            id="check_battery",
            action_type="check_battery",
            parameters={},
        ),
        WorkflowStep(
            id="send_sms_emergency",
            action_type="send_sms",
            parameters={
                "phone": "$emergency_phone",
                "message": "$emergency_message",
            },
            conditions=[
                Condition(
                    condition_type="has_value",
                    left_operand="$emergency_phone",
                )
            ],
            error_handler=ErrorHandler(
                retry_count=3,  # Retry 3 times for emergencies
                retry_delay=1.0,
                on_failure="continue",
            ),
        ),
        WorkflowStep(
            id="send_whatsapp_emergency",
            action_type="send_whatsapp",
            parameters={
                "phone": "$emergency_phone",
                "message": "🆘 EMERGENCY: $emergency_message",
            },
            error_handler=ErrorHandler(
                retry_count=2,
                on_failure="continue",
            ),
        ),
    ]
    
    workflow = WorkflowDefinition(
        id="emergency_alert",
        name="Emergency Multi-Channel Alert",
        description="Send emergency alert via SMS and WhatsApp with retries",
        steps=steps,
        tags=["emergency", "critical", "messaging"],
    )
    
    context = {
        "emergency_phone": "+1-555-9999",
        "emergency_message": "Need immediate assistance at location",
    }
    
    print("\nEmergency Alert Workflow")
    print("Configuration:")
    print(f"  SMS retries: 3 attempts")
    print(f"  WhatsApp retries: 2 attempts")
    print(f"  On failure: Continue to next method")
    
    print("\nContext:")
    for key, value in context.items():
        print(f"  {key}: {value}")
    
    success, ctx, results = executor.execute_workflow(workflow, context)
    
    print("\nExecution:")
    for r in results:
        print(f"  {r.step_id}: {r.status.value}")
        if r.output:
            print(f"    Result: {r.output}")


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("FRIDAY AI - WORKFLOW EXECUTOR EXAMPLES")
    print("="*60)
    
    try:
        example_1_basic_messaging()
        example_2_screenshot_analysis()
        example_3_reminder_automation()
        example_4_custom_workflow()
        example_5_emergency_workflow()
        
        print("\n" + "="*60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("="*60)
        print("\nKey Features Demonstrated:")
        print("  [+] Pre-built example workflows")
        print("  [+] Custom workflow creation")
        print("  [+] Context passing and variable resolution")
        print("  [+] Conditional execution logic")
        print("  [+] Error handling and retry strategies")
        print("  [+] Multi-step automation chains")
        print("\nFor more details, see WORKFLOW_EXECUTOR_README.md")
        
    except Exception as e:
        print(f"\n[!] Example failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
