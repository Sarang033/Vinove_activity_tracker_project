# Workstatus-Python-Agent

# User Activity Monitor

## Overview
The **User Activity Monitor** is a Python-based desktop application designed to monitor and log user activity in real-time on a Windows system. The application tracks key presses, mouse clicks, active window usage, and captures screenshots of the active window. The logs and screenshots are automatically uploaded to an S3 bucket for secure storage.

## Features
- **Activity Monitoring:** Tracks key presses, mouse clicks, active window usage time.
- **Screenshot Capture:** Captures and displays screenshots of the currently active window.
- **S3 Integration**: Automatically uploads activity logs and screenshots to an Amazon S3 bucket for secure cloud storage.
- **Console-based Application**: activity logs are now monitored via the console.
- **Real-time Updates**: Activity logs and screenshots are updated every 5 minutes.

## Dependencies
The following libraries are required to run the project:

- **cx_Freeze:** Used for packaging the Python script into an executable.
- **platform:** For identifying the operating system.
- **time:** For managing time-related functions.
- **datetime:** For handling date and time.
- **threading:** For running background tasks concurrently.
- **psutil:** For fetching system and process information.
- **Pillow (PIL):** For handling image processing, specifically screenshot capture and display.
- **pynput:** For monitoring keyboard and mouse events.
- **pywin32:** For Windows-specific functions such as window title fetching and screenshot capturing.

## dependencies
pip install cx_Freeze psutil Pillow pynput pywin32 


## run the project
python user_activity_monitor.py
