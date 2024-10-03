import platform
import time
from datetime import datetime, timedelta
from threading import Thread
import os
import queue
import requests
import sys
import atexit
import psutil
import shutil
from PIL import ImageGrab, Image
from pynput import keyboard, mouse
from dotenv import load_dotenv
from filelock import FileLock
import io

from s3_uploader import S3Uploader
from mfa_config import is_mfa_setup_complete, mark_mfa_setup_complete, generate_qr_code, verify_totp

if platform.system() == 'Windows':
    import win32gui

load_dotenv()

# S3 configuration
S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', 'myactivitytrackerbyvinove')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    raise ValueError("AWS credentials not found in environment variables.")

s3_uploader = S3Uploader(S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

# Activity log to store application usage data
activity_log = {}

# Variables to track user interactions
key_presses = 0
mouse_clicks = 0

# Configuration
config = {
    "capture_screenshots": True,
    "blur_screenshots": False,
    "screenshot_interval": 300,
    "screenshot_quality": 50,  # JPEG quality (0-100)
    "max_local_storage_days": 1,  # Number of days to keep local screenshots
    "screenshot_archive_dir": "archived_screenshots"
}

# Queue for storing uploads when offline
upload_queue = queue.Queue()

# File lock for single instance
LOCK_FILE = 'activity_monitor.lock'
lock = FileLock(LOCK_FILE)

# Low battery detection variables
is_laptop = hasattr(psutil, 'sensors_battery')
low_battery_threshold = 20  # Consider 15% as low battery
is_tracking_suspended = False

# Screenshot directory
SCREENSHOT_DIR = "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(config["screenshot_archive_dir"], exist_ok=True)

def fetch_active_window():
    if platform.system() == 'Windows':
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    return "Unknown"

def capture_and_compress_screenshot():
    if platform.system() == 'Windows':
        bbox = win32gui.GetWindowRect(win32gui.GetForegroundWindow())
        screenshot = ImageGrab.grab(bbox)
        
        # Compress the screenshot
        buffer = io.BytesIO()
        screenshot.save(buffer, format="JPEG", quality=config["screenshot_quality"])
        buffer.seek(0)
        
        # Convert buffer back to PIL Image
        compressed_image = Image.open(buffer)
        
        return compressed_image
    return None

def check_internet_connection():
    try:
        requests.get("http://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False

def upload_data(data_type, data, blur=False):
    if check_internet_connection():
        try:
            if data_type == "logs":
                s3_uploader.upload_logs(data)
            elif data_type == "screenshot":
                s3_uploader.upload_screenshot(data, blur=blur)
            return True
        except Exception as e:
            print(f"Failed to upload to S3. Error: {str(e)}")
            return False
    else:
        print("No internet connection. Queueing upload.")
        upload_queue.put((data_type, data, blur))
        return False

def process_upload_queue():
    while True:
        if check_internet_connection() and not upload_queue.empty():
            data_type, data, blur = upload_queue.get()
            if upload_data(data_type, data, blur):
                print(f"Successfully uploaded queued {data_type}")
            else:
                upload_queue.put((data_type, data, blur))  # Put it back in the queue if upload fails
        time.sleep(30)  # Check every 30 seconds

def check_battery_status():
    global is_tracking_suspended
    if is_laptop:
        battery = psutil.sensors_battery()
        if battery:
            percent = battery.percent
            power_plugged = battery.power_plugged
            if percent <= low_battery_threshold and not power_plugged:
                if not is_tracking_suspended:
                    print(f"Low battery detected ({percent}%). Suspending activity tracking.")
                    is_tracking_suspended = True
            elif is_tracking_suspended and (percent > low_battery_threshold or power_plugged):
                print(f"Battery level restored ({percent}%). Resuming activity tracking.")
                is_tracking_suspended = False
    return is_tracking_suspended

def manage_local_storage():
    current_time = datetime.now()
    for filename in os.listdir(SCREENSHOT_DIR):
        file_path = os.path.join(SCREENSHOT_DIR, filename)
        file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
        
        if current_time - file_creation_time > timedelta(days=config["max_local_storage_days"]):
            archive_path = os.path.join(config["screenshot_archive_dir"], filename)
            shutil.move(file_path, archive_path)
            print(f"Archived old screenshot: {filename}")

def monitor_activity():
    global key_presses, mouse_clicks

    while True:
        if check_battery_status():
            time.sleep(60)  # Check every minute when suspended
            continue

        current_time = datetime.now()
        active_window = fetch_active_window()

        if active_window not in activity_log:
            activity_log[active_window] = {
                'start_time': current_time,
                'key_presses': 0,
                'mouse_clicks': 0,
                'usage_time': 0
            }

        activity = activity_log[active_window]
        activity['usage_time'] = (current_time - activity['start_time']).total_seconds()
        activity['key_presses'] += key_presses
        activity['mouse_clicks'] += mouse_clicks

        key_presses = 0
        mouse_clicks = 0

        # Upload logs and screenshot
        upload_data("logs", activity_log)
        if config["capture_screenshots"]:
            screenshot = capture_and_compress_screenshot()
            if screenshot:
                timestamp = current_time.strftime("%Y%m%d_%H%M%S")
                local_filename = os.path.join(SCREENSHOT_DIR, f"screenshot_{timestamp}.jpg")
                screenshot.save(local_filename, "JPEG")
                upload_data("screenshot", screenshot, blur=config["blur_screenshots"])

        # Manage local storage
        manage_local_storage()

        time.sleep(config["screenshot_interval"])

def key_event_handler(key):
    global key_presses
    key_presses += 1

def mouse_event_handler(x, y, button, pressed):
    global mouse_clicks
    if pressed:
        mouse_clicks += 1

def test_s3_connection():
    try:
        s3_uploader.s3.list_objects(Bucket=S3_BUCKET_NAME, MaxKeys=1)
        print("Successfully connected to S3 bucket!")
    except Exception as e:
        print(f"Failed to connect to S3 bucket. Error: {str(e)}")

def get_user_preference():
    while True:
        choice = input("Do you want to capture blurred screenshots? (yes/no): ").lower()
        if choice in ['yes', 'no']:
            return choice == 'yes'
        print("Invalid input. Please enter 'yes' or 'no'.")

def cleanup():
    lock.release()

def verify_mfa():
    if not is_mfa_setup_complete():
        print("MFA setup is required for first-time use.")
        print("Please follow these steps to set up MFA:")
        generate_qr_code()
        print("1. Install an authenticator app on your mobile device (e.g., Google Authenticator, Authy).")
        print("2. Scan the QR code or manually enter the secret key in your authenticator app.")
        print("3. Enter the 6-digit code from your authenticator app to complete the setup.")
        
        for _ in range(3):  # Give the user 3 attempts to set up MFA
            user_token = input("Enter the 6-digit code from your authenticator app: ")
            if verify_totp(user_token):
                print("MFA setup successful.")
                mark_mfa_setup_complete()
                return True
            else:
                print("Invalid code. Please try again.")
        
        print("MFA setup failed. Please restart the application to try again.")
        return False
    else:
        print("MFA verification required.")
        for _ in range(3):  # Give the user 3 attempts
            user_token = input("Enter your 6-digit MFA code: ")
            if verify_totp(user_token):
                print("MFA verification successful.")
                return True
            else:
                print("Invalid MFA code. Please try again.")
        
        print("MFA verification failed. Exiting.")
        return False

def main():
    global config
    
    try:
        lock.acquire(timeout=1)
    except TimeoutError:
        print("Another instance of the application is already running.")
        sys.exit(1)

    atexit.register(cleanup)

    try:
        print("Starting activity monitoring...")
        
        if not verify_mfa():
            sys.exit(1)
        
        # Ask user for screenshot preference
        config["capture_screenshots"] = True  # We're always capturing screenshots in this version
        config["blur_screenshots"] = get_user_preference()
        
        print(f"Configuration: Capturing {'blurred' if config['blur_screenshots'] else 'clear'} screenshots")
        print(f"Screenshots will be compressed with quality: {config['screenshot_quality']}%")
        print(f"Local screenshots will be archived after {config['max_local_storage_days']} days")
        
        if is_laptop:
            print("Low battery detection enabled.")
        else:
            print("Low battery detection not available on this device.")
        
        Thread(target=monitor_activity, daemon=True).start()
        Thread(target=process_upload_queue, daemon=True).start()

        keyboard_listener = keyboard.Listener(on_press=key_event_handler)
        mouse_listener = mouse.Listener(on_click=mouse_event_handler)
        keyboard_listener.start()
        mouse_listener.start()

        # Keep the script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Monitoring stopped.")
    finally:
        cleanup()

if __name__ == "__main__":
    test_s3_connection()
    main()