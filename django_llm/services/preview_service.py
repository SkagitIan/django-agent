import subprocess
import os
import signal

class PreviewService:
    _process = None

    @classmethod
    def start(cls):
        if cls._process and cls._process.poll() is None:
            cls.stop()
        cls._process = subprocess.Popen(["python", "manage.py", "runserver", "8001"])

    @classmethod
    def stop(cls):
        if cls._process and cls._process.poll() is None:
            os.kill(cls._process.pid, signal.SIGTERM)
            cls._process.wait()
