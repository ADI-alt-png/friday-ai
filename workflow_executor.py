"""
Workflow Executor - Multi-step automation chains with conditional logic
Enables Friday to execute complex workflows with state management, branching, and error handling.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from collections import defaultdict
from datetime import datetime

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from action_planner import ActionPlanner, ActionResult
from android_controller import AndroidController


class StepStatus(Enum):
    """Status of a workflow step"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class ConditionType(Enum):
    """Types of conditions for step branching"""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    CONTAINS = "contains"
    BATTERY_LOW = "battery_low"
    SCREEN_ON = "screen_on"
    APP_RUNNING = "app_running"
    HAS_VALUE = "has_value"
    CUSTOM = "custom"


@dataclass
class Condition:
    """Represents a condition for step execution"""
    condition_type: str
    left_operand: str
    right_operand: Optional[str] = None
    custom_func: Optional[Callable] = None

    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context"""
        try:
            cond_type = ConditionType(self.condition_type)
            
            if cond_type == ConditionType.EQUALS:
                left_val = self._resolve_value(self.left_operand, context)
                right_val = self._resolve_value(self.right_operand, context)
                return left_val == right_val
            
            elif cond_type == ConditionType.NOT_EQUALS:
                left_val = self._resolve_value(self.left_operand, context)
                right_val = self._resolve_value(self.right_operand, context)
                return left_val != right_val
            
            elif cond_type == ConditionType.GREATER_THAN:
                left_val = self._resolve_value(self.left_operand, context)
                right_val = self._resolve_value(self.right_operand, context)
                return float(left_val) > float(right_val)
            
            elif cond_type == ConditionType.LESS_THAN:
                left_val = self._resolve_value(self.left_operand, context)
                right_val = self._resolve_value(self.right_operand, context)
                return float(left_val) < float(right_val)
            
            elif cond_type == ConditionType.CONTAINS:
                left_val = str(self._resolve_value(self.left_operand, context))
                right_val = str(self._resolve_value(self.right_operand, context))
                return right_val in left_val
            
            elif cond_type == ConditionType.HAS_VALUE:
                val = self._resolve_value(self.left_operand, context)
                return val is not None and val != ""
            
            elif cond_type == ConditionType.CUSTOM:
                if self.custom_func:
                    return self.custom_func(context)
                return False
            
            return False
        except Exception as e:
            logging.warning(f"Condition evaluation failed: {e}")
            return False

    @staticmethod
    def _resolve_value(operand: str, context: Dict[str, Any]) -> Any:
        """Resolve operand - can be literal or context reference"""
        if operand.startswith("$"):
            # Context reference like $variable or $step.output
            key = operand[1:]
            return context.get(key)
        return operand


@dataclass
class ErrorHandler:
    """Error handling strategy for a step"""
    retry_count: int = 0
    retry_delay: float = 1.0
    on_failure: str = "stop"  # "stop", "continue", "execute_fallback"
    fallback_step: Optional[str] = None


@dataclass
class StepResult:
    """Result of step execution"""
    step_id: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    executed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float = 0


@dataclass
class WorkflowStep:
    """Individual step in a workflow"""
    id: str
    action_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Condition] = field(default_factory=list)
    error_handler: ErrorHandler = field(default_factory=ErrorHandler)
    timeout_seconds: float = 30.0
    parallel_safe: bool = False


@dataclass
class WorkflowDefinition:
    """Complete workflow definition"""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)


class WorkflowContext:
    """Maintains state and context across workflow steps"""

    def __init__(self):
        self.variables = {}
        self.step_results = {}
        self.start_time = time.time()
        self._lock = threading.Lock()

    def set(self, key: str, value: Any):
        """Set context variable"""
        with self._lock:
            self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get context variable"""
        with self._lock:
            return self.variables.get(key, default)

    def store_result(self, step_result: StepResult):
        """Store step result"""
        with self._lock:
            self.step_results[step_result.step_id] = step_result

    def get_result(self, step_id: str) -> Optional[StepResult]:
        """Retrieve step result"""
        with self._lock:
            return self.step_results.get(step_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for condition evaluation"""
        with self._lock:
            result = dict(self.variables)
            for step_id, step_result in self.step_results.items():
                result[f"{step_id}.output"] = step_result.output
                result[f"{step_id}.status"] = step_result.status.value
            return result


class WorkflowExecutor:
    """Executes multi-step workflows with conditional logic and state management"""

    def __init__(self, device_id: str = None, skip_device_init: bool = False):
        self.logger = logging.getLogger(__name__)
        self.action_planner = ActionPlanner()
        self.executor_id = f"executor_{int(time.time() * 1000)}"
        self.skip_device_init = skip_device_init
        
        # Initialize Android controller only if not skipping
        if not skip_device_init:
            try:
                self.android_controller = AndroidController(device_id=device_id)
            except RuntimeError as e:
                self.logger.warning(f"AndroidController init failed: {e}. Running in simulation mode.")
                self.android_controller = None
        else:
            self.android_controller = None
        
    def execute_workflow(
        self,
        workflow: WorkflowDefinition,
        initial_context: Dict[str, Any] = None,
    ) -> Tuple[bool, WorkflowContext, List[StepResult]]:
        """
        Execute a complete workflow

        Args:
            workflow: WorkflowDefinition to execute
            initial_context: Initial context variables

        Returns:
            (success: bool, context: WorkflowContext, results: List[StepResult])
        """
        context = WorkflowContext()
        if initial_context:
            for key, value in initial_context.items():
                context.set(key, value)

        results = []
        self.logger.info(f"Starting workflow: {workflow.name} ({workflow.id})")

        try:
            for step in workflow.steps:
                step_result = self._execute_step(step, context)
                results.append(step_result)
                context.store_result(step_result)

                # Handle failures
                if step_result.status == StepStatus.FAILED:
                    if step.error_handler.on_failure == "stop":
                        self.logger.error(f"Workflow stopped at step {step.id}")
                        break
                    elif step.error_handler.on_failure == "execute_fallback":
                        if step.error_handler.fallback_step:
                            self.logger.info(f"Executing fallback: {step.error_handler.fallback_step}")
                            # Find and execute fallback step
                            fallback = next((s for s in workflow.steps if s.id == step.error_handler.fallback_step), None)
                            if fallback:
                                fallback_result = self._execute_step(fallback, context)
                                results.append(fallback_result)
                                context.store_result(fallback_result)

            success = all(r.status != StepStatus.FAILED for r in results)
            self.logger.info(f"Workflow completed: {workflow.name} - Success: {success}")
            return (success, context, results)

        except Exception as e:
            self.logger.error(f"Workflow execution error: {e}")
            return (False, context, results)

    def _execute_step(self, step: WorkflowStep, context: WorkflowContext) -> StepResult:
        """Execute a single workflow step"""
        start_time = time.time()
        result = StepResult(step_id=step.id, status=StepStatus.PENDING)

        try:
            # Check conditions
            if step.conditions:
                context_dict = context.to_dict()
                all_conditions_met = all(c.evaluate(context_dict) for c in step.conditions)
                if not all_conditions_met:
                    result.status = StepStatus.SKIPPED
                    self.logger.info(f"Step {step.id} skipped - conditions not met")
                    return result

            # Execute with retry logic
            for attempt in range(1 + step.error_handler.retry_count):
                result.status = StepStatus.RUNNING
                try:
                    result.output = self._execute_action(step, context)
                    result.status = StepStatus.SUCCESS
                    self.logger.info(f"Step {step.id} succeeded")
                    break
                except Exception as e:
                    if attempt < step.error_handler.retry_count:
                        self.logger.warning(f"Step {step.id} attempt {attempt + 1} failed, retrying...")
                        time.sleep(step.error_handler.retry_delay)
                    else:
                        raise

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            self.logger.error(f"Step {step.id} failed: {e}")

        result.duration_ms = (time.time() - start_time) * 1000
        return result

    def _execute_action(self, step: WorkflowStep, context: WorkflowContext) -> Any:
        """Execute the actual action for a step"""
        action_type = step.action_type
        params = self._resolve_parameters(step.parameters, context)

        self.logger.debug(f"Executing action: {action_type} with params: {params}")

        if action_type == "send_whatsapp":
            return self._action_send_whatsapp(params)
        elif action_type == "send_sms":
            return self._action_send_sms(params)
        elif action_type == "open_app":
            return self._action_open_app(params)
        elif action_type == "close_app":
            return self._action_close_app(params)
        elif action_type == "take_screenshot":
            return self._action_take_screenshot(params)
        elif action_type == "search_contact":
            return self._action_search_contact(params, context)
        elif action_type == "set_reminder":
            return self._action_set_reminder(params)
        elif action_type == "read_text":
            return self._action_read_text(params)
        elif action_type == "check_time":
            return self._action_check_time(params)
        elif action_type == "check_battery":
            return self._action_check_battery(params)
        elif action_type == "delay":
            return self._action_delay(params)
        else:
            raise ValueError(f"Unknown action type: {action_type}")

    def _resolve_parameters(self, parameters: Dict[str, Any], context: WorkflowContext) -> Dict[str, Any]:
        """Resolve parameters - replace context references"""
        resolved = {}
        context_dict = context.to_dict()

        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                # Context reference
                ref_key = value[1:]
                resolved[key] = context_dict.get(ref_key)
            else:
                resolved[key] = value

        return resolved

    def _action_send_whatsapp(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send WhatsApp message"""
        phone = params.get("phone")
        message = params.get("message")
        
        if not phone or not message:
            raise ValueError("WhatsApp requires 'phone' and 'message' parameters")

        if self.android_controller:
            success, output = self.android_controller.send_whatsapp(phone, message)
            if not success:
                raise Exception(f"Failed to send WhatsApp: {output}")
        else:
            self.logger.info(f"[SIMULATION] Sending WhatsApp to {phone}: {message}")

        return {"status": "sent", "phone": phone, "message": message}

    def _action_send_sms(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send SMS message"""
        phone = params.get("phone")
        message = params.get("message")
        
        if not phone or not message:
            raise ValueError("SMS requires 'phone' and 'message' parameters")

        if self.android_controller:
            success, output = self.android_controller.send_sms(phone, message)
            if not success:
                raise Exception(f"Failed to send SMS: {output}")
        else:
            self.logger.info(f"[SIMULATION] Sending SMS to {phone}: {message}")

        return {"status": "sent", "phone": phone, "message": message}

    def _action_open_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Open an application"""
        app_package = params.get("package")
        app_name = params.get("name", app_package)
        
        if not app_package:
            raise ValueError("open_app requires 'package' parameter")

        if self.android_controller:
            success, output = self.android_controller.open_app(app_package)
            if not success:
                raise Exception(f"Failed to open app: {output}")
        else:
            self.logger.info(f"[SIMULATION] Opening app: {app_name} ({app_package})")

        return {"status": "opened", "app": app_name, "package": app_package}

    def _action_close_app(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Close an application"""
        app_package = params.get("package")
        
        if not app_package:
            raise ValueError("close_app requires 'package' parameter")

        if self.android_controller:
            cmd = f"am force-stop {app_package}"
            success, output = self.android_controller._run_adb("shell", cmd)
            if not success:
                raise Exception(f"Failed to close app: {output}")
        else:
            self.logger.info(f"[SIMULATION] Closing app: {app_package}")

        return {"status": "closed", "package": app_package}

    def _action_take_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take screenshot"""
        save_path = params.get("save_path")
        
        if self.android_controller:
            success, output = self.android_controller.take_screenshot(save_path)
            if not success:
                raise Exception(f"Failed to take screenshot: {output}")
        else:
            self.logger.info(f"[SIMULATION] Taking screenshot to: {save_path}")
            output = save_path

        return {"status": "captured", "path": output}

    def _action_search_contact(self, params: Dict[str, Any], context: WorkflowContext) -> Dict[str, Any]:
        """Search for contact in address book"""
        contact_name = params.get("name")
        
        if not contact_name:
            raise ValueError("search_contact requires 'name' parameter")

        # Simulate contact search (in real implementation, would query device contacts)
        self.logger.info(f"Searching for contact: {contact_name}")
        
        return {"status": "searched", "contact": contact_name, "found": True}

    def _action_set_reminder(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set a reminder"""
        title = params.get("title")
        time_str = params.get("time")
        
        if not title or not time_str:
            raise ValueError("set_reminder requires 'title' and 'time' parameters")

        self.logger.info(f"Setting reminder: {title} at {time_str}")
        
        return {"status": "set", "reminder": title, "time": time_str}

    def _action_read_text(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read text from screenshot using OCR"""
        image_path = params.get("image_path")
        
        if not image_path:
            raise ValueError("read_text requires 'image_path' parameter")

        # If image_path is a dict (from previous step output), extract path
        if isinstance(image_path, dict):
            image_path = image_path.get("path", image_path)

        try:
            import pytesseract
            from PIL import Image
            
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img)
            
            return {"status": "read", "text": text, "image": image_path}
        except ImportError:
            self.logger.warning("pytesseract not available, returning placeholder")
            return {"status": "read", "text": "OCR not available", "image": image_path}
        except Exception as e:
            self.logger.warning(f"OCR failed: {e}, returning placeholder")
            return {"status": "read", "text": "[OCR unavailable]", "image": image_path}

    def _action_check_time(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check current time"""
        from datetime import datetime
        current_time = datetime.now()
        
        return {
            "status": "checked",
            "time": current_time.isoformat(),
            "hour": current_time.hour,
            "minute": current_time.minute,
        }

    def _action_check_battery(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check device battery level"""
        if self.android_controller:
            success, battery_info = self.android_controller.get_battery()
            if not success:
                raise Exception("Failed to get battery info")
        else:
            self.logger.info("[SIMULATION] Checking battery")
            battery_info = {"level": 85, "status": "Good"}

        return {"status": "checked", "battery": battery_info}

    def _action_delay(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for specified duration"""
        seconds = params.get("seconds", 1)
        
        self.logger.info(f"Waiting {seconds} seconds")
        time.sleep(seconds)
        
        return {"status": "completed", "duration": seconds}

    def load_workflow_from_yaml(self, yaml_path: str) -> WorkflowDefinition:
        """Load workflow definition from YAML file"""
        if not YAML_AVAILABLE:
            raise RuntimeError("PyYAML not installed. Use load_workflow_from_json instead.")
        
        try:
            with open(yaml_path, 'r') as f:
                data = yaml.safe_load(f)
            return self._parse_workflow_dict(data)
        except Exception as e:
            self.logger.error(f"Failed to load YAML workflow: {e}")
            raise

    def load_workflow_from_json(self, json_path: str) -> WorkflowDefinition:
        """Load workflow definition from JSON file"""
        try:
            with open(json_path, 'r') as f:
                data = json.load(f)
            return self._parse_workflow_dict(data)
        except Exception as e:
            self.logger.error(f"Failed to load JSON workflow: {e}")
            raise

    def _parse_workflow_dict(self, data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse workflow from dictionary"""
        steps = []
        
        for step_data in data.get("steps", []):
            conditions = []
            for cond_data in step_data.get("conditions", []):
                condition = Condition(
                    condition_type=cond_data.get("type"),
                    left_operand=cond_data.get("left"),
                    right_operand=cond_data.get("right"),
                )
                conditions.append(condition)

            error_handler = ErrorHandler(
                retry_count=step_data.get("error_handler", {}).get("retry_count", 0),
                retry_delay=step_data.get("error_handler", {}).get("retry_delay", 1.0),
                on_failure=step_data.get("error_handler", {}).get("on_failure", "stop"),
            )

            step = WorkflowStep(
                id=step_data.get("id"),
                action_type=step_data.get("action"),
                parameters=step_data.get("params", {}),
                conditions=conditions,
                error_handler=error_handler,
                timeout_seconds=step_data.get("timeout", 30.0),
                parallel_safe=step_data.get("parallel_safe", False),
            )
            steps.append(step)

        workflow = WorkflowDefinition(
            id=data.get("id"),
            name=data.get("name"),
            description=data.get("description", ""),
            steps=steps,
            version=data.get("version", "1.0"),
            tags=data.get("tags", []),
        )
        
        return workflow


class ExampleWorkflows:
    """Pre-built example workflows"""

    @staticmethod
    def send_whatsapp_to_contact() -> WorkflowDefinition:
        """
        Example: Send WhatsApp and open contact
        Steps: open WhatsApp → search contact → send message
        """
        steps = [
            WorkflowStep(
                id="open_whatsapp",
                action_type="open_app",
                parameters={"package": "com.whatsapp", "name": "WhatsApp"},
            ),
            WorkflowStep(
                id="search_contact",
                action_type="search_contact",
                parameters={"name": "$contact_name"},
            ),
            WorkflowStep(
                id="send_message",
                action_type="send_whatsapp",
                parameters={
                    "phone": "$contact_phone",
                    "message": "$message_text",
                },
                error_handler=ErrorHandler(retry_count=2, on_failure="continue"),
            ),
        ]

        return WorkflowDefinition(
            id="whatsapp_contact",
            name="Send WhatsApp to Contact",
            description="Open WhatsApp, search contact, and send message",
            steps=steps,
            tags=["messaging", "whatsapp"],
        )

    @staticmethod
    def screenshot_and_analyze() -> WorkflowDefinition:
        """
        Example: Screenshot and analyze
        Steps: take screenshot → read text → save result
        """
        steps = [
            WorkflowStep(
                id="capture",
                action_type="take_screenshot",
                parameters={"save_path": "friday_output/workflow_screenshot.png"},
            ),
            WorkflowStep(
                id="analyze",
                action_type="read_text",
                parameters={"image_path": "$capture.output"},
            ),
            WorkflowStep(
                id="delay",
                action_type="delay",
                parameters={"seconds": 1},
            ),
        ]

        return WorkflowDefinition(
            id="screenshot_analyze",
            name="Screenshot and Analyze",
            description="Take screenshot and extract text using OCR",
            steps=steps,
            tags=["device", "screenshot", "analysis"],
        )

    @staticmethod
    def reminder_workflow() -> WorkflowDefinition:
        """
        Example: Reminder workflow
        Steps: check time → if match time → open app → set reminder
        """
        steps = [
            WorkflowStep(
                id="check_time",
                action_type="check_time",
                parameters={},
            ),
            WorkflowStep(
                id="open_calendar",
                action_type="open_app",
                parameters={"package": "com.android.calendar", "name": "Calendar"},
                conditions=[
                    Condition(
                        condition_type="equals",
                        left_operand="$check_time.hour",
                        right_operand="14",
                    )
                ],
            ),
            WorkflowStep(
                id="set_reminder",
                action_type="set_reminder",
                parameters={
                    "title": "$reminder_title",
                    "time": "$reminder_time",
                },
                conditions=[
                    Condition(
                        condition_type="equals",
                        left_operand="$open_calendar.status",
                        right_operand="opened",
                    )
                ],
                error_handler=ErrorHandler(retry_count=1, on_failure="continue"),
            ),
        ]

        return WorkflowDefinition(
            id="reminder",
            name="Reminder Workflow",
            description="Check time and set reminder if conditions match",
            steps=steps,
            tags=["reminder", "calendar"],
        )


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


if __name__ == "__main__":
    # Example usage
    executor = WorkflowExecutor()

    # Execute example workflow
    workflow = ExampleWorkflows.screenshot_and_analyze()
    initial_context = {
        "contact_name": "John",
        "contact_phone": "+1234567890",
        "message_text": "Hello!",
        "reminder_title": "Team Meeting",
        "reminder_time": "14:00",
    }

    success, context, results = executor.execute_workflow(workflow, initial_context)
    
    print(f"\nWorkflow completed: {success}")
    print(f"Results: {len(results)} steps executed")
    for result in results:
        print(f"  - {result.step_id}: {result.status.value} ({result.duration_ms:.1f}ms)")
