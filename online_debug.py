#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Online Debug Script
Connect to remote server and receive red aircraft situation data
"""

import socket
import threading
import json
import time
import sys
import datetime

# Configuration parameters
REMOTE_IP = '180.1.80.238'
REMOTE_PORT = 1010
LOCAL_IP = '180.1.80.129'
LOCAL_PORT = 10113

def log_with_timestamp(message):
    """Print message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

class OnlineDebugger:
    def __init__(self):
        self.running = True
        self.remote_socket = None
        self.local_socket = None
        self.client_count = 0
        self.message_count = 0
        log_with_timestamp("OnlineDebugger initialized")
        log_with_timestamp(f"Target remote server: {REMOTE_IP}:{REMOTE_PORT}")
        log_with_timestamp(f"Local listening address: {LOCAL_IP}:{LOCAL_PORT}")

    def connect_to_remote(self):
        """Connect to remote server"""
        log_with_timestamp("Attempting to connect to remote server...")
        try:
            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            log_with_timestamp("Socket created successfully")
            
            # Set socket timeout for connection
            self.remote_socket.settimeout(10)
            log_with_timestamp(f"Connecting to {REMOTE_IP}:{REMOTE_PORT}...")
            
            self.remote_socket.connect((REMOTE_IP, REMOTE_PORT))
            self.remote_socket.settimeout(None)  # Remove timeout after connection
            
            log_with_timestamp(f'Successfully connected to remote server {REMOTE_IP}:{REMOTE_PORT}')
            return True
        except socket.timeout:
            log_with_timestamp(f'Connection timeout to remote server {REMOTE_IP}:{REMOTE_PORT}')
            return False
        except ConnectionRefusedError:
            log_with_timestamp(f'Connection refused by remote server {REMOTE_IP}:{REMOTE_PORT}')
            return False
        except Exception as e:
            log_with_timestamp(f'Failed to connect to remote server: {e}')
            return False

    def start_local_server(self):
        """Start local server to receive red aircraft situation data"""
        log_with_timestamp("Starting local server...")
        try:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            log_with_timestamp(f"Binding to {LOCAL_IP}:{LOCAL_PORT}...")
            
            self.local_socket.bind((LOCAL_IP, LOCAL_PORT))
            self.local_socket.listen(5)
            log_with_timestamp(f'Local server started successfully, listening on {LOCAL_IP}:{LOCAL_PORT}')
            log_with_timestamp("Waiting for client connections...")
            
            while self.running:
                try:
                    log_with_timestamp("Accepting new connections...")
                    client_socket, addr = self.local_socket.accept()
                    self.client_count += 1
                    log_with_timestamp(f'[Client #{self.client_count}] New connection from {addr}')
                    
                    # Create thread to handle client connection
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr, self.client_count)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    log_with_timestamp(f'[Client #{self.client_count}] Handler thread started')
                    
                except socket.error as e:
                    if self.running:
                        log_with_timestamp(f'Error accepting connection: {e}')
                        
        except Exception as e:
            log_with_timestamp(f'Failed to start local server: {e}')

    def handle_client(self, client_socket, addr, client_id):
        """Handle client connection"""
        log_with_timestamp(f'[Client #{client_id}] Starting to handle connection from {addr}')
        try:
            while self.running:
                log_with_timestamp(f'[Client #{client_id}] Waiting for data...')
                data = client_socket.recv(4096)
                if not data:
                    log_with_timestamp(f'[Client #{client_id}] No data received, closing connection')
                    break
                    
                self.message_count += 1
                log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Received {len(data)} bytes')
                
                # Parse received situation data
                try:
                    message = data.decode('utf-8')
                    log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Decoded message: {message[:100]}{"..." if len(message) > 100 else ""}')
                    
                    # Try to parse JSON format situation data
                    try:
                        situation_data = json.loads(message)
                        log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Successfully parsed JSON data')
                        self.process_situation_data(situation_data, client_id)
                    except json.JSONDecodeError as e:
                        log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] JSON decode error: {e}')
                        log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Processing as plain text')
                        
                except UnicodeDecodeError as e:
                    log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Unicode decode error: {e}')
                    log_with_timestamp(f'[Client #{client_id}] [Message #{self.message_count}] Received binary data of {len(data)} bytes')
                    
        except Exception as e:
            log_with_timestamp(f'[Client #{client_id}] Error handling client connection: {e}')
        finally:
            client_socket.close()
            log_with_timestamp(f'[Client #{client_id}] Connection with {addr} closed')

    def process_situation_data(self, data, client_id):
        """Process situation data"""
        log_with_timestamp(f'[Client #{client_id}] Processing situation data...')
        if isinstance(data, dict):
            log_with_timestamp(f'[Client #{client_id}] Data is dictionary with {len(data)} keys: {list(data.keys())}')
            
            if 'red_aircraft' in data:
                aircraft_count = len(data["red_aircraft"])
                log_with_timestamp(f'[Client #{client_id}] Red aircraft count: {aircraft_count}')
                
                for i, aircraft in enumerate(data['red_aircraft']):
                    aircraft_id = aircraft.get("id", "Unknown")
                    aircraft_type = aircraft.get("type", "Unknown")
                    longitude = aircraft.get("longitude", 0)
                    latitude = aircraft.get("latitude", 0)
                    altitude = aircraft.get("altitude", 0)
                    speed = aircraft.get("speed", 0)
                    heading = aircraft.get("heading", 0)
                    status = aircraft.get("status", "Unknown")
                    
                    log_with_timestamp(f'[Client #{client_id}] Aircraft #{i+1}: ID={aircraft_id}, Type={aircraft_type}, '
                                     f'Pos=({longitude}, {latitude}), Alt={altitude}, Speed={speed}, '
                                     f'Heading={heading}, Status={status}')
            
            if 'timestamp' in data:
                log_with_timestamp(f'[Client #{client_id}] Data timestamp: {data["timestamp"]}')
                
            if 'blue_aircraft' in data:
                blue_count = len(data["blue_aircraft"])
                log_with_timestamp(f'[Client #{client_id}] Blue aircraft count: {blue_count}')
                
            if 'parameters' in data:
                params = data["parameters"]
                log_with_timestamp(f'[Client #{client_id}] Parameters: {params}')
        else:
            log_with_timestamp(f'[Client #{client_id}] Data content (non-dict): {str(data)[:200]}{"..." if len(str(data)) > 200 else ""}')

    def send_to_remote(self, data):
        """Send data to remote server"""
        if self.remote_socket:
            try:
                if isinstance(data, dict):
                    json_data = json.dumps(data, ensure_ascii=False)
                    log_with_timestamp(f'Sending JSON data to remote server: {json_data[:100]}{"..." if len(json_data) > 100 else ""}')
                    self.remote_socket.send(json_data.encode('utf-8'))
                else:
                    log_with_timestamp(f'Sending text data to remote server: {str(data)[:100]}{"..." if len(str(data)) > 100 else ""}')
                    self.remote_socket.send(str(data).encode('utf-8'))
                log_with_timestamp('Data sent successfully to remote server')
            except Exception as e:
                log_with_timestamp(f'Failed to send data to remote server: {e}')
        else:
            log_with_timestamp('Cannot send data: no remote connection established')

    def run(self):
        """Run debugger"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('Starting online debugger...')
        log_with_timestamp('=' * 50)
        
        # Connect to remote server
        if self.connect_to_remote():
            log_with_timestamp('Remote connection established, starting local server...')
            
            # Start local server thread
            server_thread = threading.Thread(target=self.start_local_server)
            server_thread.daemon = True
            server_thread.start()
            log_with_timestamp('Local server thread started')
            
            try:
                log_with_timestamp('Debugger running, press Ctrl+C to exit...')
                log_with_timestamp('Monitoring connections and data flow...')
                
                # Print status every 30 seconds
                status_counter = 0
                while self.running:
                    time.sleep(1)
                    status_counter += 1
                    if status_counter % 30 == 0:
                        log_with_timestamp(f'Status: {self.client_count} total clients, {self.message_count} total messages processed')
                        
            except KeyboardInterrupt:
                log_with_timestamp('\nReceived exit signal (Ctrl+C)')
        else:
            log_with_timestamp('Failed to establish remote connection, exiting...')
        
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('Cleaning up resources...')
        self.running = False
        
        if self.remote_socket:
            try:
                self.remote_socket.close()
                log_with_timestamp('Remote connection closed')
            except Exception as e:
                log_with_timestamp(f'Error closing remote connection: {e}')
            
        if self.local_socket:
            try:
                self.local_socket.close()
                log_with_timestamp('Local server closed')
            except Exception as e:
                log_with_timestamp(f'Error closing local server: {e}')
                
        log_with_timestamp(f'Final statistics: {self.client_count} clients served, {self.message_count} messages processed')
        log_with_timestamp('Cleanup completed')
        log_with_timestamp('=' * 50)


if __name__ == '__main__':
    debugger = OnlineDebugger()
    try:
        debugger.run()
    except Exception as e:
        log_with_timestamp(f'Program exited with exception: {e}')
        import traceback
        log_with_timestamp('Full traceback:')
        traceback.print_exc()
        debugger.cleanup()