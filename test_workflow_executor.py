"""Test workflow executor functionality"""

import sys
sys.path.insert(0, '.')

from workflow_executor import (
    WorkflowExecutor,
    ExampleWorkflows,
    WorkflowDefinition,
    WorkflowStep,
    Condition,
    ConditionType,
    StepStatus,
    WorkflowContext,
    ErrorHandler,
)


def test_context_management():
    """Test context management"""
    ctx = WorkflowContext()
    ctx.set('test_var', 'value123')
    assert ctx.get('test_var') == 'value123'
    print('[+] Context management works')


def test_condition_evaluation():
    """Test condition evaluation"""
    ctx = WorkflowContext()
    ctx.set('test_var', 'value123')
    
    # Test equals condition
    cond = Condition(
        condition_type='equals',
        left_operand='$test_var',
        right_operand='value123'
    )
    ctx_dict = ctx.to_dict()
    result = cond.evaluate(ctx_dict)
    assert result == True
    print('[+] Condition evaluation (equals) works')
    
    # Test not_equals condition
    cond2 = Condition(
        condition_type='not_equals',
        left_operand='$test_var',
        right_operand='other'
    )
    assert cond2.evaluate(ctx_dict) == True
    print('[+] Condition evaluation (not_equals) works')
    
    # Test has_value condition
    cond3 = Condition(
        condition_type='has_value',
        left_operand='$test_var'
    )
    assert cond3.evaluate(ctx_dict) == True
    print('[+] Condition evaluation (has_value) works')


def test_example_workflows():
    """Test example workflow creation"""
    wf1 = ExampleWorkflows.send_whatsapp_to_contact()
    assert len(wf1.steps) == 3
    assert wf1.steps[0].id == 'open_whatsapp'
    print(f'[+] WhatsApp workflow: {wf1.name} ({len(wf1.steps)} steps)')
    
    wf2 = ExampleWorkflows.screenshot_and_analyze()
    assert len(wf2.steps) == 3
    assert wf2.steps[0].id == 'capture'
    print(f'[+] Screenshot workflow: {wf2.name} ({len(wf2.steps)} steps)')
    
    wf3 = ExampleWorkflows.reminder_workflow()
    assert len(wf3.steps) == 3
    assert wf3.steps[0].id == 'check_time'
    print(f'[+] Reminder workflow: {wf3.name} ({len(wf3.steps)} steps)')


def test_workflow_definition():
    """Test workflow definition creation"""
    step1 = WorkflowStep(
        id='step1',
        action_type='delay',
        parameters={'seconds': 1},
    )
    
    step2 = WorkflowStep(
        id='step2',
        action_type='delay',
        parameters={'seconds': 2},
        conditions=[
            Condition(
                condition_type='has_value',
                left_operand='$step1.output'
            )
        ],
    )
    
    workflow = WorkflowDefinition(
        id='test_workflow',
        name='Test Workflow',
        description='Test workflow',
        steps=[step1, step2],
    )
    
    assert len(workflow.steps) == 2
    assert workflow.name == 'Test Workflow'
    print('[+] Workflow definition creation works')


def test_error_handler():
    """Test error handler configuration"""
    handler = ErrorHandler(
        retry_count=3,
        retry_delay=0.5,
        on_failure='continue',
    )
    
    assert handler.retry_count == 3
    assert handler.on_failure == 'continue'
    print('[+] Error handler configuration works')


def run_all_tests():
    """Run all tests"""
    print("Running workflow executor tests...\n")
    
    try:
        test_context_management()
        test_condition_evaluation()
        test_example_workflows()
        test_workflow_definition()
        test_error_handler()
        
        print('\n[+] All tests passed!')
        return True
    except Exception as e:
        print(f'\n[-] Test failed: {e}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
