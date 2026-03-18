# Test for controlling audio with ssh
# When the start button is clicked on the flask app, recording service is started via ssh
# When the stop button is clicked on the flask app, recording service is stopped via ssh
# Every second, the hub checks to see if the satellite is recording

# NOTE: New setup idea. satellite --ssh-> hub, recording flag stored on hub is checked by the satellite
# to determine if it should be recording. if the ssh connection fails, the recording stops

import paramiko

HOSTNAME = "health-trac-pi"
USERNAME = "healthtrac"
PASSWORD = "Tubeless-Ice-Retract-Stock" # TODO: This is incredibly insecure and needs to be changed after proof of concept

ssh = paramiko.SSHClient()
ssh.connect(HOSTNAME, username=USERNAME, password=PASSWORD)
ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command("ls")
