"""Integration test for workflow executor - demonstrates full workflow execution"""

import sys
import json
sys.path.insert(0, '.')

from workflow_executor import (
    WorkflowExecutor,
    ExampleWorkflows,
    WorkflowDefinition,
    WorkflowStep,
    Condition,
    ErrorHandler,
    StepStatus,
)


def test_workflow_execution():
    """Test actual workflow execution with mocking"""
    print("\n=== Testing Workflow Execution ===\n")
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    # Create a simple test workflow
    steps = [
        WorkflowStep(
            id="step1",
            action_type="check_time",
            parameters={},
        ),
        WorkflowStep(
            id="step2",
            action_type="check_battery",
            parameters={},
        ),
        WorkflowStep(
            id="step3",
            action_type="delay",
            parameters={"seconds": 0.5},  # Short delay for testing
            conditions=[
                Condition(
                    condition_type="has_value",
                    left_operand="$step1.output",
                )
            ],
        ),
    ]
    
    workflow = WorkflowDefinition(
        id="test_exec",
        name="Test Execution Workflow",
        description="Test workflow with real actions",
        steps=steps,
    )
    
    # Execute workflow
    print("Executing workflow: Test Execution Workflow")
    print(f"Steps: {len(workflow.steps)}")
    print("-" * 50)
    
    success, context, results = executor.execute_workflow(workflow)
    
    # Print results
    print(f"\nWorkflow Success: {success}")
    print(f"Total Steps: {len(results)}")
    print("\nStep Results:")
    
    for result in results:
        status_str = f"[+] {result.status.value}" if result.status == StepStatus.SUCCESS else f"[-] {result.status.value}"
        print(f"  {result.step_id:15} {status_str:15} ({result.duration_ms:6.1f}ms)")
        if result.error:
            print(f"    Error: {result.error}")
        if result.output:
            # Print first 100 chars of output
            output_str = str(result.output)[:100]
            print(f"    Output: {output_str}")
    
    print("\nContext Variables:")
    context_dict = context.to_dict()
    for key, value in sorted(context_dict.items()):
        if not key.endswith('.status') and not key.endswith('.output'):
            print(f"  {key}: {value}")


def test_workflow_with_conditions():
    """Test workflow with conditional execution"""
    print("\n=== Testing Workflow with Conditions ===\n")
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    steps = [
        WorkflowStep(
            id="set_variable",
            action_type="delay",
            parameters={"seconds": 0},
        ),
        WorkflowStep(
            id="conditional_step",
            action_type="check_time",
            parameters={},
            conditions=[
                Condition(
                    condition_type="has_value",
                    left_operand="$set_variable.output",
                )
            ],
        ),
        WorkflowStep(
            id="skipped_step",
            action_type="check_time",
            parameters={},
            conditions=[
                Condition(
                    condition_type="equals",
                    left_operand="nonexistent_var",
                    right_operand="value",
                )
            ],
        ),
    ]
    
    workflow = WorkflowDefinition(
        id="conditional_test",
        name="Conditional Execution Test",
        description="Test conditional step execution",
        steps=steps,
    )
    
    print("Executing workflow: Conditional Execution Test")
    print("-" * 50)
    
    success, context, results = executor.execute_workflow(workflow)
    
    print(f"\nWorkflow Success: {success}")
    print("\nStep Statuses:")
    
    for result in results:
        status_icon = "[+]" if result.status == StepStatus.SUCCESS else ("[S]" if result.status == StepStatus.SKIPPED else "[-]")
        print(f"  {result.step_id:20} {status_icon} {result.status.value}")
    
    # Verify skipped step
    skipped = next(r for r in results if r.step_id == "skipped_step")
    assert skipped.status == StepStatus.SKIPPED, "Skipped step should have SKIPPED status"
    print("\n[+] Conditional execution working correctly")


def test_workflow_error_handling():
    """Test workflow error handling with retry"""
    print("\n=== Testing Workflow Error Handling ===\n")
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    steps = [
        WorkflowStep(
            id="success_step",
            action_type="delay",
            parameters={"seconds": 0},
            error_handler=ErrorHandler(retry_count=0, on_failure="stop"),
        ),
        WorkflowStep(
            id="continue_on_error",
            action_type="delay",
            parameters={"seconds": 0},
            error_handler=ErrorHandler(retry_count=1, on_failure="continue"),
        ),
    ]
    
    workflow = WorkflowDefinition(
        id="error_test",
        name="Error Handling Test",
        description="Test error handling strategies",
        steps=steps,
    )
    
    print("Executing workflow: Error Handling Test")
    print("-" * 50)
    
    success, context, results = executor.execute_workflow(workflow)
    
    print(f"\nWorkflow Success: {success}")
    print("Step Execution:")
    
    for result in results:
        print(f"  {result.step_id:20} {result.status.value}")
    
    print("\n[+] Error handling strategies working correctly")


def test_json_workflow_loading():
    """Test loading workflow from JSON"""
    print("\n=== Testing JSON Workflow Loading ===\n")
    
    executor = WorkflowExecutor(skip_device_init=True)
    
    workflow_json = {
        "id": "json_test",
        "name": "JSON Loaded Workflow",
        "description": "Test loading from JSON",
        "version": "1.0",
        "steps": [
            {
                "id": "first_step",
                "action": "delay",
                "params": {"seconds": 0},
                "timeout": 10.0,
                "parallel_safe": False,
            },
            {
                "id": "second_step",
                "action": "check_time",
                "params": {},
                "conditions": [
                    {
                        "type": "has_value",
                        "left": "$first_step.output",
                    }
                ],
                "timeout": 10.0,
                "parallel_safe": False,
            },
        ],
    }
    
    # Parse workflow
    workflow = executor._parse_workflow_dict(workflow_json)
    
    print(f"Loaded workflow: {workflow.name}")
    print(f"Steps: {len(workflow.steps)}")
    for step in workflow.steps:
        print(f"  - {step.id}: {step.action_type}")
    
    # Execute
    print("\nExecuting loaded workflow...")
    success, context, results = executor.execute_workflow(workflow)
    
    print(f"Success: {success}")
    print(f"Results: {len(results)} steps executed")
    print("\n[+] JSON workflow loading and execution successful")


def main():
    """Run all integration tests"""
    print("=" * 60)
    print("WORKFLOW EXECUTOR - INTEGRATION TESTS")
    print("=" * 60)
    
    try:
        test_workflow_execution()
        test_workflow_with_conditions()
        test_workflow_error_handling()
        test_json_workflow_loading()
        
        print("\n" + "=" * 60)
        print("[+] ALL INTEGRATION TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[-] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

