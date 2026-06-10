# HealthTRAC Architecture
## Sensor Architecture
### FSR/IMU
ESP32 Hosts web server connected to network hosted by pi hub. Makes routes available to get data from sensor buffer
- Calling API yield JSON in the following format where the arrays are populated with the current data
```json
{
    "timestamps": [],
    "sensors": [[], [], [], ...]
}
```
- After calling the API, the json is returned, and the data buffers on the ESP32 are cleared
- Length of timestamp array has to match length of each sensor array

### Hub
The hub manages hosting the network for the ESP32s to connect to and periodically queries their APIs
- Every `query_frequency` seconds, the hub will call methods for collecting json data from the FSR and IMU ESP32s.
- These methods will first save the data to their corresponding `.csv` files in `data/`
- Next they will update rolling global buffers on the server which will be used for the dashboard
    - Each sensor will have a rolling buffer for the last 2 minutes of data
    - Each sensor will also have a downsampled rolling 24 hour buffer. In this ones case, we will just take one the highest magnitude datapoint from the current query. (If we query the ESP32 every 5 seconds, then the polling rate for this buffer will be 1/5hz)

### Dashboard
The hub will also need to host API routes for the dashboard to get graphing data from. The graphs on the dashboard should be looking for labels (the scale for the x-axis), and (x,y) data for each sensor.
- Use the following json as a template where data is drawn from the rolling buffers (2 minute or 24-hour) on the hub and each graph on the dashboard has a corresponding API route
```json
{
    "labels": [0, 100, 200, 300, 400, 500],
    "data": [
            [
                {"x": 17770320, "y": 0.0},
                {"x": 17770323, "y": 0.5},
                {"x": 17770326, "y": 0.866},
                {"x": 17770329, "y": 1.0},
                {"x": 17770332, "y": 0.866},
                {"x": 17770335, "y": 0.5},
                {"x": 17770338, "y": 0.0},
                {"x": 17770341, "y": -0.5},
                {"x": 17770344, "y": -0.866},
                {"x": 17770347, "y": -1.0},
                {"x": 17770350, "y": -0.866},
                {"x": 17770353, "y": -0.5},
            ],
            [
                {"x": 17770320, "y": 0.0},
                {"x": 17770323, "y": 25.0},
                {"x": 17770326, "y": 43.3},
                {"x": 17770329, "y": 50.0},
                {"x": 17770332, "y": 43.3},
                {"x": 17770335, "y": 25.0},
                {"x": 17770338, "y": 0.0},
                {"x": 17770341, "y": -25.0},
                {"x": 17770344, "y": -43.3},
                {"x": 17770347, "y": -50.0},
                {"x": 17770350, "y": -43.3},
                {"x": 17770353, "y": -25.0},
            ]
    ]
}
```