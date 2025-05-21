import shutil
import os
import sys
from app_utils.stream_capture import StreamCapture

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def clear_directory(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

if __name__ == "__main__":
    clear_directory("violations")
    monitor = StreamCapture()
    monitor.start_capture()