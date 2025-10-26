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
        self.mqtt_client_publish: Optional[mqtt.Client] = None  # Client for publishing SOC
        self.mqtt_client_trigger: Optional[mqtt.Client] = None  # Client for trigger monitoring
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
        """Setup MQTT clients and connect to brokers."""
        try:
            mqtt_config = self.config['MQTT']
            
            # Setup publishing client (for SOC data)
            client_id_publish = mqtt_config.get('client_id_publish', 'kia_niro_ev_soc_publisher')
            self.mqtt_client_publish = mqtt.Client(client_id=client_id_publish)
            
            # Set username and password for publish broker if provided
            username_publish = mqtt_config.get('username_publish', '').strip()
            password_publish = mqtt_config.get('password_publish', '').strip()
            if username_publish:
                self.mqtt_client_publish.username_pw_set(username_publish, password_publish)
            
            # Set callbacks for publish client
            self.mqtt_client_publish.on_connect = self._on_mqtt_connect_publish
            self.mqtt_client_publish.on_disconnect = self._on_mqtt_disconnect_publish
            
            # Connect to publish broker
            broker_publish = mqtt_config.get('broker_publish', 'localhost')
            port_publish = mqtt_config.getint('port_publish', 1883)
            
            print(f"Connecting to MQTT publish broker {broker_publish}:{port_publish}...")
            self.mqtt_client_publish.connect(broker_publish, port_publish, 60)
            self.mqtt_client_publish.loop_start()
            
            # Setup trigger client (for monitoring status)
            client_id_trigger = mqtt_config.get('client_id_trigger', 'kia_niro_ev_trigger_monitor')
            self.mqtt_client_trigger = mqtt.Client(client_id=client_id_trigger)
            
            # Set username and password for trigger broker if provided
            username_trigger = mqtt_config.get('username_trigger', '').strip()
            password_trigger = mqtt_config.get('password_trigger', '').strip()
            if username_trigger:
                self.mqtt_client_trigger.username_pw_set(username_trigger, password_trigger)
            
            # Set callbacks for trigger client
            self.mqtt_client_trigger.on_connect = self._on_mqtt_connect_trigger
            self.mqtt_client_trigger.on_disconnect = self._on_mqtt_disconnect_trigger
            self.mqtt_client_trigger.on_message = self._on_mqtt_message
            
            # Connect to trigger broker
            broker_trigger = mqtt_config.get('broker_trigger', 'localhost')
            port_trigger = mqtt_config.getint('port_trigger', 1883)
            
            print(f"Connecting to MQTT trigger broker {broker_trigger}:{port_trigger}...")
            self.mqtt_client_trigger.connect(broker_trigger, port_trigger, 60)
            self.mqtt_client_trigger.loop_start()
            
            return True
            
        except Exception as e:
            print(f"Error setting up MQTT: {e}")
            return False
    
    def _on_mqtt_connect_publish(self, client, userdata, flags, rc):
        """Callback for when MQTT publish client connects."""
        if rc == 0:
            print("✓ Connected to MQTT publish broker")
        else:
            print(f"✗ Failed to connect to MQTT publish broker, return code: {rc}")
    
    def _on_mqtt_disconnect_publish(self, client, userdata, rc):
        """Callback for when MQTT publish client disconnects."""
        if rc != 0:
            print(f"⚠ Unexpected MQTT publish broker disconnection (code: {rc})")
    
    def _on_mqtt_connect_trigger(self, client, userdata, flags, rc):
        """Callback for when MQTT trigger client connects."""
        if rc == 0:
            print("✓ Connected to MQTT trigger broker")
            # Subscribe to trigger topic
            mqtt_config = self.config['MQTT']
            trigger_topic = mqtt_config.get('trigger_topic', 'openevse/status')
            client.subscribe(trigger_topic)
            print(f"✓ Subscribed to trigger topic: {trigger_topic}")
        else:
            print(f"✗ Failed to connect to MQTT trigger broker, return code: {rc}")
    
    def _on_mqtt_disconnect_trigger(self, client, userdata, rc):
        """Callback for when MQTT trigger client disconnects."""
        if rc != 0:
            print(f"⚠ Unexpected MQTT trigger broker disconnection (code: {rc})")
    
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
    
    def _reconnect_vehicle(self, retry_delay: float) -> bool:
        """Reconnect to the vehicle after a connection failure."""
        # Close existing connection if any
        if self.elm:
            try:
                self.elm.close()
                print("✓ Closed previous vehicle connection")
            except Exception as e:
                print(f"⚠ Error closing previous connection: {e}")
            self.elm = None
            self.kia = None
        
        # Attempt to reconnect indefinitely until running is False
        attempt = 1
        while self.running:
            print(f"\nReconnection attempt {attempt}")
            if self._connect_vehicle():
                return True
            
            print(f"Retrying in {retry_delay} seconds...")
            # Sleep in small increments to allow for graceful shutdown
            sleep_time = 0
            while sleep_time < retry_delay and self.running:
                time.sleep(1)
                sleep_time += 1
            
            if not self.running:
                print("\n⚠ Shutdown requested during reconnection")
                return False
            
            attempt += 1
        
        return False

    
    def _publish_soc(self, soc: float, timestamp: datetime):
        """Publish SOC to MQTT topics."""
        if not self.mqtt_client_publish:
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
            self.mqtt_client_publish.publish(soc_topic_1, soc_payload, qos=qos, retain=retain)
            print(f"  → Published to {soc_topic_1}")
        
        if soc_topic_2:
            self.mqtt_client_publish.publish(soc_topic_2, soc_payload, qos=qos, retain=retain)
            print(f"  → Published to {soc_topic_2}")
        
        # Publish timestamp of last successful update
        if timestamp_topic:
            timestamp_payload = json.dumps({
                "timestamp": timestamp.isoformat(),
                "unix": int(timestamp.timestamp())
            })
            self.mqtt_client_publish.publish(timestamp_topic, timestamp_payload, qos=qos, retain=retain)
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
        retry_delay = polling_config.getfloat('retry_delay', 10)
        
        self.running = True  # Set running flag before connection attempts
        
        connected = False
        attempt = 0 
        while self.running and not connected:
            attempt += 1
            print(f"\nConnection attempt {attempt}")
            if self._connect_vehicle():
                connected = True
                break
            
            print(f"Retrying in {retry_delay} seconds...")
            # Sleep in small increments to allow for graceful shutdown
            sleep_time = 0
            while sleep_time < retry_delay and self.running:
                time.sleep(1)
                sleep_time += 1
        
        if not connected:
            print("\nFailed to connect to vehicle. Exiting.")
            self.cleanup()
            return
        
        # Main polling loop
        interval = polling_config.getfloat('interval', 30)
        print(f"\n✓ Setup complete. Polling every {interval} seconds.")
        print("Press Ctrl+C to stop.\n")
        
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while self.running:
            try:
                # Only read and publish if polling is enabled by trigger
                if self.polling_enabled:
                    success = self._read_and_publish_soc()
                    if success:
                        consecutive_errors = 0  # Reset error counter on success
                    else:
                        consecutive_errors += 1
                        print(f"⚠ Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                        
                        # Reconnect to vehicle if too many consecutive errors
                        if consecutive_errors >= max_consecutive_errors:
                            print(f"\n⚠ Too many consecutive errors. Attempting to reconnect to vehicle...")
                            self._reconnect_vehicle(retry_delay)
                            consecutive_errors = 0
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
                print(f"✗ Unexpected error in main loop: {e}")
                consecutive_errors += 1
                print(f"⚠ Consecutive errors: {consecutive_errors}/{max_consecutive_errors}")
                
                # Attempt to reconnect to vehicle
                if consecutive_errors >= max_consecutive_errors:
                    print(f"\n⚠ Too many consecutive errors. Attempting to reconnect to vehicle...")
                    self._reconnect_vehicle(retry_delay)
                    consecutive_errors = 0
                else:
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
        
        if self.mqtt_client_publish:
            try:
                self.mqtt_client_publish.loop_stop()
                self.mqtt_client_publish.disconnect()
                print("✓ Disconnected from MQTT publish broker")
            except Exception as e:
                print(f"⚠ Error disconnecting from MQTT publish broker: {e}")
        
        if self.mqtt_client_trigger:
            try:
                self.mqtt_client_trigger.loop_stop()
                self.mqtt_client_trigger.disconnect()
                print("✓ Disconnected from MQTT trigger broker")
            except Exception as e:
                print(f"⚠ Error disconnecting from MQTT trigger broker: {e}")
        
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
