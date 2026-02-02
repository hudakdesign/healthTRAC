import os
import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

ssh.load_system_host_keys()
ssh.connect(hostname="health-trac-pi", username="healthtrac")

RECORDING_FILE = "recording_timestamp"
check_recording_command = f"cat /home/healthtrac/Projects/Hub-Audio-Test/{RECORDING_FILE}"

ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(check_recording_command)

print(ssh_stdout.read().decode())