from cx_Freeze import setup, Executable

setup(
    name = "User Activity Monitor",
    version = "1.0",
   capture_screenshots = True,
   blur_screenshots = True, 
    description = "A tool to monitor user activity in real-time",
    executables = [Executable("user_activity_monitor.py", base="Win32GUI")]
)
