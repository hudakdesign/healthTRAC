import json


def wifi_setup() -> dict:
    """Gets network credentials from user and returns a dict of credentials"""

    print("---WiFi Setup---")

    wifi_config = {}
    wifi_config["ssid"] = input("Network SSID: ")
    wifi_config["password"] = input("Network password: ")

    return wifi_config


def subsystem_setup() -> dict:
    """Gets subsystem info from user and returns config for each subsystem"""

    def fsr_setup() -> dict:
        """Helps generate config for fsr"""
        return {"type": "fsr"}

    def imu_setup() -> dict:
        """Helps generate config for imu"""
        return {"type": "imu"}

    def mic_setup() -> dict:
        """Helps generate config for mic array"""
        return {"type": "mic"}

    suffix_list = ["alpha", "beta", "gamma", "delta", "epsilon"]

    print("---Subsystem Setup---")

    subsystem_config = {}
    fsr_count, imu_count, mic_count = 0, 0, 0
    currently_configuring = True

    while currently_configuring:
        print("Select a subsystem to configure or `done`:")
        print("1) fsr")
        print("2) imu")
        print("3) mic")
        print("0) done")
        selection = input()

        match selection:
            case "1":
                subsystem_config[f"fsr-{suffix_list[fsr_count]}"] = fsr_setup()
                fsr_count += 1
            case "2":
                subsystem_config[f"imu-{suffix_list[imu_count]}"] = imu_setup()
                imu_count += 1
            case "3":
                subsystem_config[f"mic-{suffix_list[mic_count]}"] = mic_setup()
                mic_count += 1
            case "0":
                currently_configuring = False
            case _:
                print("INVALID INPUT. Make sure to enter a digit")

    return subsystem_config


def review_config() -> None:
    """Displays the config to the user for review"""
    pass


def write_config(file_path) -> None:
    """Writes the config to a file"""
    pass


def configure_subsystems(file_path):
    """Generates header files for each subsystem from provided config"""
    pass


def main():
    print(wifi_setup())
    print(subsystem_setup())


if __name__ == "__main__":
    main()
