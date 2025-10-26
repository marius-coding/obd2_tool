# MQTT SOC Publisher for Kia Niro EV

This application reads the State of Charge (SOC) from a Kia Niro EV and publishes it to MQTT topics at configurable intervals.

## Features

- ✅ Reads SOC periodically from Kia Niro EV via BLE connection
- ✅ Publishes to two configurable MQTT topics
- ✅ Publishes timestamp of last successful reading
- ✅ Only updates SOC when vehicle responds successfully (no updates on errors)
- ✅ **Conditional polling based on MQTT trigger topic** (e.g., only poll when charging)
- ✅ Fully configurable via INI file
- ✅ Graceful shutdown on Ctrl+C
- ✅ Auto-discovery of BLE OBD devices
- ✅ Connection retry logic
- ✅ Mock mode for testing

## Installation

### Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
pip install paho-mqtt
```

Or install paho-mqtt directly:

```bash
pip install paho-mqtt
```

## Configuration

The application is configured using the `mqtt_soc_config.ini` file. Copy and edit this file to match your setup:

### MQTT Settings

```ini
[MQTT]
broker = localhost          # MQTT broker address
port = 1883                # MQTT broker port
username =                 # Optional: MQTT username
password =                 # Optional: MQTT password
client_id = kia_niro_ev_soc_publisher

# Two SOC topics - customize as needed
soc_topic_1 = kia/niro_ev/battery/soc
soc_topic_2 = home/ev/soc

# Timestamp topic for last successful update
timestamp_topic = kia/niro_ev/battery/last_update

# Trigger topic - only poll when this topic has the trigger value
# This allows conditional polling (e.g., only when OpenEVSE is charging)
trigger_topic = openevse/status
trigger_value = active

qos = 1                    # MQTT Quality of Service (0, 1, or 2)
retain = true              # Retain messages
```

### Vehicle Settings

```ini
[Vehicle]
# BLE address of your OBD adapter (leave empty for auto-discovery)
ble_address = 

# Connection timeout in seconds
connection_timeout = 10.0

# Use mock connection for testing
use_mock = false
```

### Polling Settings

```ini
[Polling]
# Polling interval in seconds
interval = 30

# Number of retries on connection failure
max_connection_retries = 5

# Delay between connection retries
retry_delay = 10
```

## Usage

### Basic Usage

Run with default configuration file (`mqtt_soc_config.ini` in current directory):

```bash
python mqtt_soc_publisher.py
```

Or make it executable and run directly:

```bash
chmod +x mqtt_soc_publisher.py
./mqtt_soc_publisher.py
```

### Custom Configuration File

Specify a different configuration file:

```bash
python mqtt_soc_publisher.py /path/to/custom_config.ini
```

### Testing with Mock Data

To test without a real vehicle, set `use_mock = true` in the configuration file or create a test configuration:

```ini
[Vehicle]
use_mock = true
```

Then run:

```bash
python mqtt_soc_publisher.py
```

## MQTT Message Format

### SOC Topics

The SOC is published as JSON with the following format:

```json
{
  "value": 85.5,
  "unit": "%",
  "timestamp": "2025-10-26T14:30:45.123456"
}
```

### Timestamp Topic

The last update timestamp is published as JSON:

```json
{
  "timestamp": "2025-10-26T14:30:45.123456",
  "unix": 1729951845
}
```

## Behavior

- **On successful reading**: SOC and timestamp are published to all configured topics
- **On failed reading**: No MQTT messages are published; previous values remain (due to retain flag)
- **On trigger topic match**: Polling is enabled and vehicle SOC is read at the configured interval
- **On trigger topic mismatch**: Polling is paused, waiting for the trigger condition
- **On connection loss**: Application will retry according to configuration
- **On Ctrl+C**: Graceful shutdown, closes all connections properly

## Trigger-Based Polling

The application subscribes to a configurable trigger topic (e.g., `openevse/status`) and only polls the vehicle when the topic value matches the configured trigger value (e.g., `active`). This is useful for:

- **Charging scenarios**: Only poll SOC when OpenEVSE is actively charging
- **Power management**: Reduce unnecessary vehicle wake-ups
- **Cost savings**: Minimize BLE communication overhead

### Example: OpenEVSE Integration

When OpenEVSE publishes `active` to `openevse/status`, the application will start polling. When it publishes `disabled` or any other value, polling stops.

```
openevse/status = "active"   → Polling ENABLED
openevse/status = "disabled" → Polling DISABLED
openevse/status = "sleeping" → Polling DISABLED
```

## Example Home Assistant Integration

Add to your `configuration.yaml`:

```yaml
mqtt:
  sensor:
    - name: "Kia Niro EV Battery SOC"
      state_topic: "kia/niro_ev/battery/soc"
      value_template: "{{ value_json.value }}"
      unit_of_measurement: "%"
      device_class: battery
      
    - name: "Kia Niro EV Last Update"
      state_topic: "kia/niro_ev/battery/last_update"
      value_template: "{{ value_json.timestamp }}"
      device_class: timestamp
```

## Running as a Service

### systemd Service (Linux)

Create a service file `/etc/systemd/system/kia-soc-mqtt.service`:

```ini
[Unit]
Description=Kia Niro EV SOC MQTT Publisher
After=network.target bluetooth.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/home/yourusername/obd2_tool
ExecStart=/usr/bin/python3 /home/yourusername/obd2_tool/mqtt_soc_publisher.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable kia-soc-mqtt.service
sudo systemctl start kia-soc-mqtt.service
```

Check status:

```bash
sudo systemctl status kia-soc-mqtt.service
```

View logs:

```bash
sudo journalctl -u kia-soc-mqtt.service -f
```

## Troubleshooting

### No BLE devices found

- Ensure your BLE adapter is enabled: `bluetoothctl power on`
- Make sure the OBD adapter is powered (vehicle ignition on)
- Try specifying the BLE address directly in the config
- Check adapter is in range

### Connection timeouts

- Increase `connection_timeout` in configuration
- Ensure vehicle is in accessory or ON mode
- Check for BLE interference

### MQTT connection failures

- Verify broker address and port
- Check username/password if using authentication
- Test broker connectivity: `mosquitto_pub -h localhost -t test -m "test"`

### SOC not updating

- Check terminal output for error messages
- Verify vehicle ECU is responsive
- Try increasing polling interval to reduce ECU load

## License

See the LICENSE file in the root directory.
