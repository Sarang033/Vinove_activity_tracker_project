import platform
import time
from datetime import datetime
from threading import Thread

import psutil
from PIL import ImageGrab
from pynput import keyboard, mouse

from s3_uploader import S3Uploader

if platform.system() == 'Windows':
    import win32gui

# S3 configuration
S3_BUCKET_NAME = 'myactivitytrackerbyvinove'
AWS_ACCESS_KEY_ID = 'AKIA6ODU3XBWQ2AUZK4E'
AWS_SECRET_ACCESS_KEY = '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'

s3_uploader = S3Uploader(S3_BUCKET_NAME, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

# Activity log to store application usage data
activity_log = {}

# Variables to track user interactions
key_presses = 0
mouse_clicks = 0

def fetch_active_window():
    if platform.system() == 'Windows':
        return win32gui.GetWindowText(win32gui.GetForegroundWindow())
    return "Unknown"

def capture_screenshot():
    if platform.system() == 'Windows':
        bbox = win32gui.GetWindowRect(win32gui.GetForegroundWindow())
        return ImageGrab.grab(bbox)
    return None

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

        screenshot = capture_screenshot()
        
        # Upload logs and screenshot to S3
        try:
            s3_uploader.upload_logs(activity_log)
            if screenshot:
                s3_uploader.upload_screenshot(screenshot)
        except Exception as e:
            print(f"Failed to upload to S3. Error: {str(e)}")

        time.sleep(300)

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

def main():
    print("Starting activity monitoring...")
    Thread(target=monitor_activity, daemon=True).start()

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

if __name__ == "__main__":
    test_s3_connection()
    main()