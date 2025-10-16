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

# Configuration parameters
REMOTE_IP = '180.1.80.238'
REMOTE_PORT = 1010
LOCAL_IP = '180.1.80.129'
LOCAL_PORT = 10113

class OnlineDebugger:
    def __init__(self):
        self.running = True
        self.remote_socket = None
        self.local_socket = None

    def connect_to_remote(self):
        """Connect to remote server"""
        try:
            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.remote_socket.connect((REMOTE_IP, REMOTE_PORT))
            print(f'Successfully connected to remote server {REMOTE_IP}:{REMOTE_PORT}')
            return True
        except Exception as e:
            print(f'Failed to connect to remote server: {e}')
            return False

    def start_local_server(self):
        """Start local server to receive red aircraft situation data"""
        try:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.local_socket.bind((LOCAL_IP, LOCAL_PORT))
            self.local_socket.listen(5)
            print(f'Local server started, listening on {LOCAL_IP}:{LOCAL_PORT}')
            
            while self.running:
                try:
                    client_socket, addr = self.local_socket.accept()
                    print(f'Received connection from {addr}')
                    
                    # Create thread to handle client connection
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f'Error accepting connection: {e}')
                        
        except Exception as e:
            print(f'Failed to start local server: {e}')

    def handle_client(self, client_socket, addr):
        """Handle client connection"""
        try:
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                    
                # Parse received situation data
                try:
                    message = data.decode('utf-8')
                    print(f'Received red aircraft situation data: {message}')
                    
                    # Try to parse JSON format situation data
                    try:
                        situation_data = json.loads(message)
                        self.process_situation_data(situation_data)
                    except json.JSONDecodeError:
                        print('Received non-JSON format data, processing as text')
                        
                except UnicodeDecodeError:
                    print('Received binary data')
                    
        except Exception as e:
            print(f'Error handling client connection: {e}')
        finally:
            client_socket.close()
            print(f'Connection with {addr} closed')

    def process_situation_data(self, data):
        """Process situation data"""
        print('Processing situation data:')
        if isinstance(data, dict):
            if 'red_aircraft' in data:
                print(f'  Red aircraft count: {len(data["red_aircraft"])}')
                for aircraft in data['red_aircraft']:
                    print(f'    Aircraft ID: {aircraft.get("id", "Unknown")}, '
                          f'Type: {aircraft.get("type", "Unknown")}, '
                          f'Position: ({aircraft.get("longitude", 0)}, {aircraft.get("latitude", 0)})')
            
            if 'timestamp' in data:
                print(f'  Timestamp: {data["timestamp"]}')
        else:
            print(f'  Data content: {data}')

    def send_to_remote(self, data):
        """Send data to remote server"""
        if self.remote_socket:
            try:
                if isinstance(data, dict):
                    data = json.dumps(data, ensure_ascii=False)
                self.remote_socket.send(data.encode('utf-8'))
                print(f'Sent data to remote server: {data}')
            except Exception as e:
                print(f'Failed to send data to remote server: {e}')

    def run(self):
        """Run debugger"""
        print('Starting online debugger...')
        
        # Connect to remote server
        if self.connect_to_remote():
            # Start local server thread
            server_thread = threading.Thread(target=self.start_local_server)
            server_thread.daemon = True
            server_thread.start()
            
            try:
                print('Debugger running, press Ctrl+C to exit...')
                while self.running:
                    time.sleep(1)
            except KeyboardInterrupt:
                print('\nReceived exit signal')
        
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        print('Cleaning up resources...')
        self.running = False
        
        if self.remote_socket:
            self.remote_socket.close()
            print('Remote connection closed')
            
        if self.local_socket:
            self.local_socket.close()
            print('Local server closed')

if __name__ == '__main__':
    debugger = OnlineDebugger()
    try:
        debugger.run()
    except Exception as e:
        print(f'Program exited with exception: {e}')
        debugger.cleanup()