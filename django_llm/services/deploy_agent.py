import os
import paramiko
import requests
from dotenv import load_dotenv

load_dotenv()

class DeployAgent:
    @staticmethod
    def publish():
        hostname = os.environ.get("SSH_HOST")
        username = os.environ.get("SSH_USER")
        key_filename = os.environ.get("SSH_KEY_FILENAME")
        project_dir = os.environ.get("PROJECT_DIR")

        commands = [
            f"cd {project_dir}",
            "git pull",
            "pip install -r requirements.txt",
            "python manage.py migrate",
            "sudo systemctl restart gunicorn"
        ]

        with paramiko.SSHClient() as client:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname, username=username, key_filename=key_filename)
            for command in commands:
                stdin, stdout, stderr = client.exec_command(command)
                print(stdout.read().decode())
                print(stderr.read().decode())

        DeployAgent.verify_health()

    @staticmethod
    def verify_health():
        print("Verifying health...")
        try:
            # We'll use a placeholder URL for now.
            response = requests.get("http://example.com/health/")
            if response.status_code == 200:
                print("Health check successful.")
            else:
                print(f"Health check failed with status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Health check failed with error: {e}")
