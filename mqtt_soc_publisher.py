#!/usr/bin/env python3
"""
MQTT SOC Publisher for Kia Niro EV

This application reads the State of Charge (SOC) from a Kia Niro EV at 
configurable intervals and publishes it to MQTT targets.

Features:
- Reads SOC periodically from Kia Niro EV via BLE
- Publishes to two configurable MQTT topics
- Publishes timestamp of last successful reading
- Only updates SOC when vehicle responds successfully
- Configurable via INI file
"""

import sys
import os
import time
import configparser
import json
import signal
from datetime import datetime
from typing import Optional

# Add parent directory to path to import driver module
sys.path.insert(0, os.path.dirname(__file__))

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("Error: paho-mqtt library not installed.")
    print("Please install it with: pip install paho-mqtt")
    sys.exit(1)

from driver.elm327 import ELM327
from driver.kia_niro_ev import KiaNiroEV
from driver.ble_connection import BLEConnection
from driver.mock_serial import MockConnection


class SOCPublisher:
    """MQTT publisher for Kia Niro EV State of Charge."""
    
    def __init__(self, config_file: str = "mqtt_soc_config.ini"):
        """Initialize the SOC publisher with configuration."""
        self.config = self._load_config(config_file)
        self.mqtt_client: Optional[mqtt.Client] = None
        self.elm: Optional[ELM327] = None
        self.kia: Optional[KiaNiroEV] = None
        self.running = False
        self.last_soc: Optional[float] = None
        self.last_update_time: Optional[datetime] = None
        self.polling_enabled = False  # Only poll when enabled by MQTT trigger
        self.trigger_status = "unknown"  # Track the trigger status
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _load_config(self, config_file: str) -> configparser.ConfigParser:
        """Load and validate configuration from INI file."""
        config = configparser.ConfigParser()
        
        if not os.path.exists(config_file):
            print(f"Error: Configuration file '{config_file}' not found.")
            sys.exit(1)
        
        config.read(config_file)
        
        # Validate required sections
        required_sections = ['MQTT', 'Vehicle', 'Polling']
        for section in required_sections:
            if section not in config:
                print(f"Error: Missing required section '[{section}]' in config file.")
                sys.exit(1)
        
        return config
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print("\n\nShutdown signal received. Cleaning up...")
        self.running = False
    
    def _setup_mqtt(self) -> bool:
        """Setup MQTT client and connect to broker."""
        try:
            mqtt_config = self.config['MQTT']
            
            # Create MQTT client
            client_id = mqtt_config.get('client_id', 'kia_niro_ev_soc_publisher')
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
            # Set username and password if provided
            username = mqtt_config.get('username', '').strip()
            password = mqtt_config.get('password', '').strip()
            if username:
                self.mqtt_client.username_pw_set(username, password)
            
            # Set callbacks
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            # Connect to broker
            broker = mqtt_config.get('broker', 'localhost')
            port = mqtt_config.getint('port', 1883)
            
            print(f"Connecting to MQTT broker {broker}:{port}...")
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()
            
            return True
            
        except Exception as e:
            print(f"Error setting up MQTT: {e}")
            return False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects."""
        if rc == 0:
            print("✓ Connected to MQTT broker")
            # Subscribe to trigger topic
            mqtt_config = self.config['MQTT']
            trigger_topic = mqtt_config.get('trigger_topic', 'openevse/status')
            client.subscribe(trigger_topic)
            print(f"✓ Subscribed to trigger topic: {trigger_topic}")
        else:
            print(f"✗ Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects."""
        if rc != 0:
            print(f"⚠ Unexpected MQTT disconnection (code: {rc})")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Callback for when a message is received on subscribed topic."""
        try:
            mqtt_config = self.config['MQTT']
            trigger_value = mqtt_config.get('trigger_value', 'active').strip()
            
            payload = msg.payload.decode('utf-8').strip()
            self.trigger_status = payload
            
            # Check if payload matches trigger value
            old_state = self.polling_enabled
            self.polling_enabled = (payload.lower() == trigger_value.lower())
            
            if old_state != self.polling_enabled:
                status = "ENABLED" if self.polling_enabled else "DISABLED"
                print(f"\n⚡ Polling {status} (trigger topic: '{payload}')")
        except Exception as e:
            print(f"⚠ Error processing trigger message: {e}")
    
    def _connect_vehicle(self) -> bool:
        """Connect to the Kia Niro EV via BLE or mock."""
        vehicle_config = self.config['Vehicle']
        use_mock = vehicle_config.getboolean('use_mock', False)
        
        print("\nConnecting to vehicle...")
        
        try:
            if use_mock:
                print("Using mock connection (simulated data)")
                mock_conn = MockConnection()
                mock_conn.open()
                self.elm = ELM327(mock_conn)
                self.elm.initialize()
                print("✓ Connected to mock device")
            else:
                # Get BLE address
                ble_address = vehicle_config.get('ble_address', '').strip()
                timeout = vehicle_config.getfloat('connection_timeout', 10.0)
                
                # Auto-discover if no address provided
                if not ble_address:
                    print("No BLE address configured, scanning for OBD devices (5s)...")
                    devices = BLEConnection.discover_obd_devices(timeout=5.0)
                    if not devices:
                        print("✗ No OBD BLE devices found.")
                        return False
                    
                    picked = devices[0]
                    ble_address = picked['address']
                    print(f"Discovered device: {picked['name']} @ {ble_address}")
                
                print(f"Opening BLE connection to {ble_address}...")
                conn = BLEConnection(address=ble_address, timeout=timeout)
                conn.open()
                self.elm = ELM327(conn)
                self.elm.initialize()
                print(f"✓ Connected to BLE device: {ble_address}")
            
            # Create Kia Niro EV interface
            self.kia = KiaNiroEV(self.elm)
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to vehicle: {e}")
            return False
    
    def _publish_soc(self, soc: float, timestamp: datetime):
        """Publish SOC to MQTT topics."""
        if not self.mqtt_client:
            return
        
        mqtt_config = self.config['MQTT']
        qos = mqtt_config.getint('qos', 1)
        retain = mqtt_config.getboolean('retain', True)
        
        # Publish to both SOC topics
        soc_topic_1 = mqtt_config.get('soc_topic_1')
        soc_topic_2 = mqtt_config.get('soc_topic_2')
        timestamp_topic = mqtt_config.get('timestamp_topic')
        
        # Publish SOC value
        soc_payload = json.dumps({
            "value": round(soc, 1),
            "unit": "%",
            "timestamp": timestamp.isoformat()
        })
        
        if soc_topic_1:
            self.mqtt_client.publish(soc_topic_1, soc_payload, qos=qos, retain=retain)
            print(f"  → Published to {soc_topic_1}")
        
        if soc_topic_2:
            self.mqtt_client.publish(soc_topic_2, soc_payload, qos=qos, retain=retain)
            print(f"  → Published to {soc_topic_2}")
        
        # Publish timestamp of last successful update
        if timestamp_topic:
            timestamp_payload = json.dumps({
                "timestamp": timestamp.isoformat(),
                "unix": int(timestamp.timestamp())
            })
            self.mqtt_client.publish(timestamp_topic, timestamp_payload, qos=qos, retain=retain)
            print(f"  → Published timestamp to {timestamp_topic}")
    
    def _read_and_publish_soc(self) -> bool:
        """Read SOC from vehicle and publish to MQTT."""
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reading SOC...")
            
            # Read SOC from vehicle
            soc = self.kia.get_soc()
            current_time = datetime.now()
            
            print(f"✓ SOC: {soc:.1f}%")
            
            # Update state
            self.last_soc = soc
            self.last_update_time = current_time
            
            # Publish to MQTT
            self._publish_soc(soc, current_time)
            
            return True
            
        except Exception as e:
            print(f"✗ Error reading SOC: {e}")
            print("  SOC will not be updated (keeping previous value)")
            return False
    
    def run(self):
        """Main run loop."""
        print("=" * 60)
        print("Kia Niro EV SOC MQTT Publisher")
        print("=" * 60)
        
        # Setup MQTT
        if not self._setup_mqtt():
            print("Failed to setup MQTT. Exiting.")
            return
        
        # Wait a moment for MQTT to connect
        time.sleep(2)
        
        # Connect to vehicle with retry logic
        polling_config = self.config['Polling']
        max_retries = polling_config.getint('max_connection_retries', 5)
        retry_delay = polling_config.getfloat('retry_delay', 10)
        
        connected = False
        for attempt in range(1, max_retries + 1):
            print(f"\nConnection attempt {attempt}/{max_retries}")
            if self._connect_vehicle():
                connected = True
                break
            
            if attempt < max_retries:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
        
        if not connected:
            print("\nFailed to connect to vehicle after multiple attempts. Exiting.")
            self.cleanup()
            return
        
        # Main polling loop
        interval = polling_config.getfloat('interval', 30)
        print(f"\n✓ Setup complete. Polling every {interval} seconds.")
        print("Press Ctrl+C to stop.\n")
        
        self.running = True
        
        while self.running:
            try:
                # Only read and publish if polling is enabled by trigger
                if self.polling_enabled:
                    self._read_and_publish_soc()
                else:
                    # Just show waiting status periodically
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    print(f"\n[{current_time}] Waiting for trigger (current status: '{self.trigger_status}')...")
                
                # Wait for next interval
                if self.polling_enabled:
                    print(f"Waiting {interval} seconds until next reading...")
                
                # Sleep in small increments to allow for graceful shutdown
                sleep_time = 0
                while sleep_time < interval and self.running:
                    time.sleep(1)
                    sleep_time += 1
                
            except Exception as e:
                print(f"✗ Unexpected error: {e}")
                print(f"Retrying in {interval} seconds...")
                time.sleep(interval)
        
        # Cleanup
        self.cleanup()
    
    def cleanup(self):
        """Clean up connections."""
        print("\nCleaning up connections...")
        
        if self.elm:
            try:
                self.elm.close()
                print("✓ Closed vehicle connection")
            except Exception as e:
                print(f"⚠ Error closing vehicle connection: {e}")
        
        if self.mqtt_client:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                print("✓ Disconnected from MQTT broker")
            except Exception as e:
                print(f"⚠ Error disconnecting from MQTT: {e}")
        
        print("✓ Done")


def main():
    """Main entry point."""
    # Check for config file argument
    config_file = "mqtt_soc_config.ini"
    
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    
    # Create and run publisher
    publisher = SOCPublisher(config_file)
    publisher.run()


if __name__ == "__main__":
    main()
