import platform
import time
from datetime import datetime
from threading import Thread
import os
import queue
import requests
import sys
import atexit

import psutil
from PIL import ImageGrab
from pynput import keyboard, mouse
from dotenv import load_dotenv
from filelock import FileLock

from s3_uploader import S3Uploader

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
    "screenshot_interval": 5
}

# Queue for storing uploads when offline
upload_queue = queue.Queue()

# File lock for single instance
LOCK_FILE = 'activity_monitor.lock'
lock = FileLock(LOCK_FILE)

def fetch_active_window():
    if platform.system() == 'Windows':
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    return "Unknown"

def capture_screenshot():
    if platform.system() == 'Windows':
        bbox = win32gui.GetWindowRect(win32gui.GetForegroundWindow())
        return ImageGrab.grab(bbox)
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

def monitor_activity():
    global key_presses, mouse_clicks

    while True:
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
            screenshot = capture_screenshot()
            if screenshot:
                upload_data("screenshot", screenshot, blur=config["blur_screenshots"])

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
        
        # Ask user for screenshot preference
        config["capture_screenshots"] = True  # We're always capturing screenshots in this version
        config["blur_screenshots"] = get_user_preference()
        
        print(f"Configuration: Capturing {'blurred' if config['blur_screenshots'] else 'clear'} screenshots")
        
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