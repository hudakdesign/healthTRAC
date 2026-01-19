def check_recording_status():
    with open("recording", 'r') as infile:
        line = infile.readline()
        line = line.strip()
        print(line)
        if line == "True":
            print("Is True")
            return True
        else:
            print("Is False")
            return False

def toggle_recording():
    rec = check_recording_status()

    with open("recording", 'w') as outfile:
        if rec:
            outfile.write("False")
        else:
            outfile.write("True")

if __name__ == "__main__":
    toggle_recording()