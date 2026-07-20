"""
Android Controller - Direct Android device control via ADB
Enables Friday to send texts, open apps, and control Android phones
"""

import subprocess
import json
import os
import re
import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Safe actions whitelist - only these operations are allowed
SAFE_ACTIONS = {
    "send_sms": True,
    "send_whatsapp": True,
    "open_app": True,
    "close_app": True,
    "take_screenshot": True,
    "get_screen_text": True,
    "tap": True,
    "swipe": True,
    "type_text": True,
    "press_key": True,
    "get_device_info": True,
    "list_apps": True,
    "get_battery": True,
    "get_notifications": True,
}

# Apps blocklist - these apps cannot be controlled
BLOCKED_APPS = {
    "com.google.android.gms.auth",
    "com.android.systemui.keyguard",
    "com.android.settings.password",
    "com.google.android.apps.authenticator2",
}

# Commands blocklist - dangerous operations
BLOCKED_COMMANDS = [
    "reboot", "shutdown", "factory", "wipe", "format",
    "uninstall", "pm remove", "rm -rf", "su -c"
]

@dataclass
class AndroidDevice:
    device_id: str
    model: str
    android_version: str
    battery: int

class AndroidController:
    """Controls Android device via ADB"""
    
    def __init__(self, device_id: str = None):
        self.device_id = device_id
        self.adb_path = self._find_adb()
        self.connected = False
        self.device_info = None
        
    def _find_adb(self) -> str:
        """Find ADB executable in system PATH or Android SDK"""
        common_paths = [
            "adb",
            os.path.expanduser("~\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe"),
            "C:\\Android\\platform-tools\\adb.exe",
        ]
        
        for path in common_paths:
            try:
                subprocess.run([path, "version"], capture_output=True, timeout=2)
                return path
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        raise RuntimeError("ADB not found. Install Android SDK platform-tools.")
    
    def _run_adb(self, *args) -> Tuple[bool, str]:
        """Execute ADB command safely"""
        try:
            cmd = [self.adb_path]
            if self.device_id:
                cmd.extend(["-s", self.device_id])
            cmd.extend(args)
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10
            )
            return (result.returncode == 0, result.stdout + result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "ADB command timeout")
        except Exception as e:
            return (False, str(e))
    
    def connect(self) -> bool:
        """Verify connection to Android device"""
        success, output = self._run_adb("devices")
        if success and "device" in output:
            self.connected = True
            self.device_info = self.get_device_info()
            return True
        return False
    
    def _validate_action(self, action: str) -> bool:
        """Check if action is safe to execute"""
        if action not in SAFE_ACTIONS:
            return False
        
        for blocked in BLOCKED_COMMANDS:
            if blocked in action.lower():
                return False
        
        return True
    
    def get_device_info(self) -> Dict:
        """Get device information"""
        success, output = self._run_adb("shell", "getprop")
        if not success:
            return {}
        
        props = {}
        for line in output.split("\n"):
            match = re.match(r"\[(.*?)\]: \[(.*?)\]", line)
            if match:
                props[match.group(1)] = match.group(2)
        
        return {
            "model": props.get("ro.product.model", "Unknown"),
            "version": props.get("ro.build.version.release", "Unknown"),
            "api_level": props.get("ro.build.version.sdk", "Unknown"),
        }
    
    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Send SMS message"""
        if not self._validate_action("send_sms"):
            return (False, "SMS sending not allowed")
        
        # Use am (Activity Manager) to open SMS app and compose
        cmd = (
            f'am start -a android.intent.action.SENDTO '
            f'--es sms_body "{message}" '
            f'sms:{phone_number}'
        )
        
        success, output = self._run_adb("shell", cmd)
        return (success, "SMS prompt opened on device" if success else output)
    
    def send_whatsapp(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """Send WhatsApp message"""
        if not self._validate_action("send_whatsapp"):
            return (False, "WhatsApp sending not allowed")
        
        # WhatsApp URL scheme
        encoded_msg = message.replace(" ", "%20").replace("\n", "%0a")
        url = f"https://wa.me/{phone_number}?text={encoded_msg}"
        
        cmd = f'am start -a android.intent.action.VIEW -d "{url}"'
        success, output = self._run_adb("shell", cmd)
        
        return (success, "WhatsApp opened on device" if success else output)
    
    def open_app(self, app_package: str) -> Tuple[bool, str]:
        """Open an application"""
        if not self._validate_action("open_app"):
            return (False, "Opening apps not allowed")
        
        if app_package in BLOCKED_APPS:
            return (False, f"App {app_package} is blocked")
        
        cmd = f"am start -n {app_package}/{self._get_launcher_activity(app_package)}"
        success, output = self._run_adb("shell", cmd)
        
        return (success, f"Opening {app_package}" if success else output)
    
    def _get_launcher_activity(self, package: str) -> str:
        """Get launcher activity for a package"""
        cmd = f"cmd package resolve-activity --brief {package}"
        success, output = self._run_adb("shell", cmd)
        
        if success and output:
            lines = output.strip().split("\n")
            return lines[0] if lines else ".MainActivity"
        return ".MainActivity"
    
    def take_screenshot(self, save_path: str = None) -> Tuple[bool, str]:
        """Take screenshot of device"""
        if not self._validate_action("take_screenshot"):
            return (False, "Screenshots not allowed")
        
        if not save_path:
            save_path = os.path.expanduser("~/friday_output/phone_screenshot.png")
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Take screenshot on device
        device_path = "/sdcard/friday_screenshot.png"
        success, _ = self._run_adb("shell", "screencap", "-p", device_path)
        
        if success:
            # Pull to computer
            success, output = self._run_adb("pull", device_path, save_path)
            if success:
                return (True, f"Screenshot saved to {save_path}")
        
        return (False, "Failed to take screenshot")
    
    def tap(self, x: int, y: int) -> Tuple[bool, str]:
        """Tap on screen at coordinates"""
        if not self._validate_action("tap"):
            return (False, "Tapping not allowed")
        
        cmd = f"input tap {x} {y}"
        success, output = self._run_adb("shell", cmd)
        
        return (success, "Tapped screen" if success else output)
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 500) -> Tuple[bool, str]:
        """Swipe on screen"""
        if not self._validate_action("swipe"):
            return (False, "Swiping not allowed")
        
        cmd = f"input swipe {x1} {y1} {x2} {y2} {duration}"
        success, output = self._run_adb("shell", cmd)
        
        return (success, "Swiped screen" if success else output)
    
    def type_text(self, text: str) -> Tuple[bool, str]:
        """Type text on device"""
        if not self._validate_action("type_text"):
            return (False, "Typing not allowed")
        
        # Escape special characters
        text = text.replace('"', '\\"').replace("$", "\\$")
        cmd = f'input text "{text}"'
        
        success, output = self._run_adb("shell", cmd)
        return (success, "Text typed" if success else output)
    
    def press_key(self, key_code: int) -> Tuple[bool, str]:
        """Press a key on device"""
        if not self._validate_action("press_key"):
            return (False, "Key press not allowed")
        
        cmd = f"input keyevent {key_code}"
        success, output = self._run_adb("shell", cmd)
        
        return (success, f"Key {key_code} pressed" if success else output)
    
    def get_battery(self) -> Tuple[bool, Dict]:
        """Get battery status"""
        if not self._validate_action("get_battery"):
            return (False, {})
        
        success, output = self._run_adb("shell", "dumpsys battery")
        
        if success:
            battery_data = {}
            for line in output.split("\n"):
                if ": " in line:
                    key, value = line.split(": ", 1)
                    battery_data[key.strip()] = value.strip()
            return (True, battery_data)
        
        return (False, {})
    
    def list_apps(self, user_only: bool = True) -> Tuple[bool, List[str]]:
        """List installed apps"""
        if not self._validate_action("list_apps"):
            return (False, [])
        
        flag = "-3" if user_only else ""
        cmd = f"pm list packages {flag}"
        success, output = self._run_adb("shell", cmd)
        
        if success:
            apps = [line.replace("package:", "") for line in output.split("\n") if line]
            return (True, apps)
        
        return (False, [])
    
    def get_notifications(self) -> Tuple[bool, List[Dict]]:
        """Get current notifications"""
        success, output = self._run_adb("shell", "dumpsys notification")
        
        if success:
            # Simple parsing - extract notification titles
            notifications = []
            for line in output.split("\n"):
                if "title=" in line:
                    notifications.append({"title": line.split("title=")[1]})
            return (True, notifications)
        
        return (False, [])


def execute_android_action(action: str, device_id: str = None, **kwargs) -> Dict:
    """
    Main entry point for executing Android actions
    Returns: {"success": bool, "result": str, "data": any}
    """
    try:
        controller = AndroidController(device_id)
        
        if not controller.connect():
            return {"success": False, "result": "Failed to connect to Android device"}
        
        # Route to appropriate action
        if action == "send_sms":
            success, result = controller.send_sms(kwargs["phone"], kwargs["message"])
        elif action == "send_whatsapp":
            success, result = controller.send_whatsapp(kwargs["phone"], kwargs["message"])
        elif action == "open_app":
            success, result = controller.open_app(kwargs["package"])
        elif action == "take_screenshot":
            success, result = controller.take_screenshot(kwargs.get("path"))
        elif action == "tap":
            success, result = controller.tap(kwargs["x"], kwargs["y"])
        elif action == "swipe":
            success, result = controller.swipe(
                kwargs["x1"], kwargs["y1"], kwargs["x2"], kwargs["y2"],
                kwargs.get("duration", 500)
            )
        elif action == "type_text":
            success, result = controller.type_text(kwargs["text"])
        elif action == "press_key":
            success, result = controller.press_key(kwargs["code"])
        elif action == "get_battery":
            success, result = controller.get_battery()
        elif action == "list_apps":
            success, result = controller.list_apps(kwargs.get("user_only", True))
        elif action == "get_device_info":
            success, result = controller.get_device_info()
        else:
            return {"success": False, "result": f"Unknown action: {action}"}
        
        return {
            "success": success,
            "result": str(result),
            "action": action,
            "device": controller.device_id
        }
    
    except Exception as e:
        return {"success": False, "result": f"Error: {str(e)}"}


# Test function
if __name__ == "__main__":
    print("[ANDROID CONTROLLER] Testing Android device connection...")
    
    try:
        controller = AndroidController()
        if controller.connect():
            print(f"✓ Connected to device")
            print(f"  Device info: {controller.device_info}")
            
            # List apps
            success, apps = controller.list_apps()
            if success:
                print(f"✓ Found {len(apps)} user apps")
        else:
            print("✗ Could not connect to device. Make sure:")
            print("  1. Android device is connected via USB")
            print("  2. USB debugging is enabled on device")
            print("  3. ADB is installed and in PATH")
    except RuntimeError as e:
        print(f"✗ {e}")
