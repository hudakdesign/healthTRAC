from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
import threading

app = Flask(__name__)

recording_state = {"is_recording": False}
audio_features = {}
recording_lock = threading.Lock()

@app.route('/')
def dashboard():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Audio Recording Dashboard</title>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            body { font-family: Arial; margin: 20px; background: #f0f0f0; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
            .control-panel { background: #e8f4f8; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            .button { padding: 15px 30px; font-size: 18px; border: none; border-radius: 5px; cursor: pointer; }
            .button.start { background: #4CAF50; color: white; }
            .button.stop { background: #f44336; color: white; }
            .button:disabled { background: #ccc; cursor: not-allowed; }
            .status { font-size: 24px; margin: 20px 0; }
            .status.recording { color: #f44336; }
            .status.stopped { color: #666; }
            .device-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }
            .device-card { background: #f9f9f9; padding: 15px; border-radius: 5px; border-left: 4px solid #2196F3; }
            .device-card h3 { margin-top: 0; color: #2196F3; }
            .feature { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee; }
            .timestamp { color: #999; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Audio Recording System</h1>
            <div class="control-panel">
                <h2>Recording Control</h2>
                <button id="startBtn" class="button start" onclick="startRecording()">Start Recording</button>
                <button id="stopBtn" class="button stop" onclick="stopRecording()" disabled>Stop Recording</button>
                <div id="status" class="status stopped">● NOT RECORDING</div>
            </div>
            <h2>Audio Devices</h2>
            <div id="devices" class="device-grid"></div>
        </div>
        <script>
            function startRecording() {
                $.post('/api/start_recording', function() {
                    $('#startBtn').prop('disabled', true);
                    $('#stopBtn').prop('disabled', false);
                    $('#status').removeClass('stopped').addClass('recording').text('● RECORDING');
                });
            }
            function stopRecording() {
                $.post('/api/stop_recording', function() {
                    $('#startBtn').prop('disabled', false);
                    $('#stopBtn').prop('disabled', true);
                    $('#status').removeClass('recording').addClass('stopped').text('● NOT RECORDING');
                });
            }
            function updateDevices() {
                $.get('/api/audio_devices', function(data) {
                    let html = '';
                    if (Object.keys(data).length === 0) {
                        html = '<p>No devices connected yet...</p>';
                    } else {
                        for (let [deviceId, info] of Object.entries(data)) {
                            html += `
                                <div class="device-card">
                                    <h3>${deviceId}</h3>
                                    <div class="feature">
                                        <span>RMS Level:</span>
                                        <strong>${info.features.rms.toFixed(1)}</strong>
                                    </div>
                                    <div class="feature">
                                        <span>Zero Crossing Rate:</span>
                                        <strong>${info.features.zero_crossing_rate.toFixed(3)}</strong>
                                    </div>
                                    <div class="timestamp">Last update: ${info.timestamp}</div>
                                </div>
                            `;
                        }
                    }
                    $('#devices').html(html);
                });
            }
            setInterval(updateDevices, 2000);
            updateDevices();
            $.get('/api/recording_state', function(data) {
                if (data.is_recording) {
                    $('#startBtn').prop('disabled', true);
                    $('#stopBtn').prop('disabled', false);
                    $('#status').removeClass('stopped').addClass('recording').text('● RECORDING');
                }
            });
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/api/recording_state', methods=['GET'])
def get_recording_state():
    with recording_lock:
        return jsonify(recording_state)

@app.route('/api/start_recording', methods=['POST'])
def start_recording():
    with recording_lock:
        recording_state["is_recording"] = True
    print(f"[HUB] Recording started at {datetime.now()}")
    return jsonify({"success": True})

@app.route('/api/stop_recording', methods=['POST'])
def stop_recording():
    with recording_lock:
        recording_state["is_recording"] = False
    print(f"[HUB] Recording stopped at {datetime.now()}")
    return jsonify({"success": True})

@app.route('/api/audio_features', methods=['POST'])
def receive_audio_features():
    data = request.json
    device_id = data.get("device_id")
    audio_features[device_id] = {
        "timestamp": data.get("timestamp"),
        "features": data.get("features")
    }
    return jsonify({"success": True})

@app.route('/api/audio_devices', methods=['GET'])
def get_audio_devices():
    return jsonify(audio_features)

if __name__ == "__main__":
    print("Starting Audio Hub Server on http://localhost:5555")
    app.run(host='0.0.0.0', port=5555, debug=False)
