import paramiko

REMOTE_HOSTNAME = "health-trac-pi"
REMOTE_USERNAME = "healthtrac"
TEST_COMMAND = "ls"

ssh = paramiko.SSHClient() # Creates an ssh client object. This is basically your ssh terminal
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy()) # Adds the server to knownhosts; prevents an error

ssh.load_system_host_keys() # Loads ssh-key from the host system (this system)
ssh.connect(hostname=REMOTE_HOSTNAME, username=REMOTE_USERNAME) # Connects to `REMOTE_HOSTNAME` as `REMOTE_USERNAME`

# Executes whatever string is given as an argument. Prints the return
def execute_command(command):
    ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(command)
    print(ssh_stdout.read().decode())

# ssh.close()

if __name__ == "__main__":
    while True:
        try:
            input("Press `Enter` to `ls`:")
            execute_command(TEST_COMMAND)
        except KeyboardInterrupt:
            ssh.close()
            raise SystemExit



# NOTE: pi hub connects to each satellite on the network using its key
# each satellit connects to the hub using their key
# pi hub "tells" the satellites to start recording
# pi hub checks if the recording service is running and displays it on the dash
# satellite checks timestamp in is_recording file, if the last timestamp is more than 5 seconds old,
# then the connection is dead. The satellite then automatically stops the recording