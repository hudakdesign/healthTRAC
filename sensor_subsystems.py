# Module containing classes for interfacing with all sensor subsystems in healthTRAC

# Classes:
class Sensor_Subsystem:
    """Generic parent class for retrieving data from sensor subsystems
    
    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
    
    """
    pass

class Microphone_Array(Sensor_Subsystem):
    """Handles retrieving data from microphone array subsystems
    
    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
    """
    pass

class Force_Sensitive_Resistor(Sensor_Subsystem):
    """Handles retrieving data from force sensitive resistor subsystems
    
    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
    """
    pass

class Inertial_Measurement_Unit(Sensor_Subsystem):
    """Handles retrieving data from microphone array subsystems
    
    Attributes:
        subsystem_url: The URL for accessing the microphone array.
        raw_data_polls: A list for containing received raw data polls.
        aggregate_data_polls_short: A ring buffer of aggregate datapoints
            used for display and debugging on the dashboard.
        aggregate_data_polls_long: A ring buffer of very low frequency
            aggregate datapoints for display and debugging on the dashboard.
    """
    pass