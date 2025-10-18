#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Online Debug Script
Connect to remote server and receive red aircraft situation data via UDP
"""

import socket
import threading
import json
import time
import sys
import datetime
import struct

# Configuration parameters
REMOTE_IP = '180.1.80.238'
REMOTE_PORT = 1010
LOCAL_IP = '180.1.80.241'
LOCAL_PORT = 5371


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
        self.remote_address = (REMOTE_IP, REMOTE_PORT)
        self.client_addresses = set()  # Track unique client addresses
        log_with_timestamp("OnlineDebugger initialized for UDP communication")
        log_with_timestamp(f"Target remote server: {REMOTE_IP}:{REMOTE_PORT}")
        log_with_timestamp(f"Local listening address: {LOCAL_IP}:{LOCAL_PORT}")

    def connect_to_remote(self):
        """Create UDP socket for remote communication"""
        log_with_timestamp("Creating UDP socket for remote communication...")
        try:
            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            log_with_timestamp("UDP socket created successfully")
            
            # Test connectivity by sending a test message
            test_message = json.dumps({"type": "connection_test", "timestamp": time.time()})
            log_with_timestamp(f"Testing UDP connection to {REMOTE_IP}:{REMOTE_PORT}...")
            
            try:
                self.remote_socket.settimeout(5)  # 5 second timeout for test
                self.remote_socket.sendto(test_message.encode('utf-8'), self.remote_address)
                log_with_timestamp("Test message sent to remote server")
                
                # Try to receive response (optional for UDP)
                try:
                    response, addr = self.remote_socket.recvfrom(1024)
                    log_with_timestamp(f"Received response from remote server: {response.decode('utf-8')[:100]}")
                except socket.timeout:
                    log_with_timestamp("No response from remote server (normal for UDP)")
                
                self.remote_socket.settimeout(None)  # Remove timeout
                log_with_timestamp(f'UDP connection to remote server {REMOTE_IP}:{REMOTE_PORT} established')
                return True
                
            except Exception as e:
                log_with_timestamp(f'UDP connection test failed: {e}')
                log_with_timestamp('Continuing anyway (UDP is connectionless)')
                self.remote_socket.settimeout(None)
                return True  # UDP is connectionless, so we continue anyway
                
        except Exception as e:
            log_with_timestamp(f'Failed to create UDP socket: {e}')
            return False

    def start_local_server(self):
        """Start local UDP server to receive red aircraft situation data"""
        log_with_timestamp("Starting local UDP server...")
        try:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            log_with_timestamp(f"Binding UDP socket to {LOCAL_IP}:{LOCAL_PORT}...")
            
            self.local_socket.bind((LOCAL_IP, LOCAL_PORT))
            log_with_timestamp(f'Local UDP server started successfully, listening on {LOCAL_IP}:{LOCAL_PORT}')
            log_with_timestamp("Waiting for UDP packets...")
            
            while self.running:
                try:
                    log_with_timestamp("Waiting for UDP data...")
                    # Set timeout to allow periodic status checks
                    self.local_socket.settimeout(1.0)
                    
                    try:
                        data, addr = self.local_socket.recvfrom(4096)
                        
                        # Track unique client addresses
                        if addr not in self.client_addresses:
                            self.client_addresses.add(addr)
                            self.client_count += 1
                            log_with_timestamp(f'[Client #{self.client_count}] New UDP client from {addr}')
                        
                        self.message_count += 1
                        log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Received {len(data)} bytes')
                        
                        # Process the received data
                        self.handle_udp_data(data, addr)
                        
                    except socket.timeout:
                        # Timeout is normal, continue loop
                        continue
                        
                except socket.error as e:
                    if self.running:
                        log_with_timestamp(f'Error receiving UDP data: {e}')
                        
        except Exception as e:
            log_with_timestamp(f'Failed to start local UDP server: {e}')

    # 10月17-由嘉伟-udp解包
    class UDPMessageParser:
        """UDP消息解析器"""
        
        @staticmethod
        def parse_message_header(data):
            """解析UDP消息头"""
            if len(data) < 26:  # 消息头固定26字节
                return None
                
            # 解析消息头：MsgID(2) + SourcePlatCode(4) + ReceivePlatCode(4) + SerialNum(4) + 
            #           CreateTime(8) + TotalPacks(1) + CurrentIndex(1) + DataLength(2)
            header = struct.unpack('<HIIIQBBH', data[:26])
            return {
                'MsgID': header[0],
                'SourcePlatCode': header[1], 
                'ReceivePlatCode': header[2],
                'SerialNum': header[3],
                'CreateTime': header[4],
                'TotalPacks': header[5],
                'CurrentIndex': header[6],
                'DataLength': header[7]
            }
        
        @staticmethod
        def parse_experiment_prep_message(data):
            """解析试验准备消息(0x0001)"""
            if len(data) < 231:  # 消息头26字节 + 消息体205字节 = 231字节
                return None
                
            # ExperimentID(4) + ExperimentFileNo(1) + ExperimentName(100) + ExperimentFileName(100)
            experiment_id = struct.unpack('<I', data[26:30])[0]
            experiment_file_no = struct.unpack('<b', data[30:31])[0]
            experiment_name = data[31:131].rstrip(b'\x00').decode('utf-8', errors='ignore')
            experiment_file_name = data[131:231].rstrip(b'\x00').decode('utf-8', errors='ignore')
            
            return {
                'ExperimentID': experiment_id,
                'ExperimentFileNo': experiment_file_no,
                'ExperimentName': experiment_name,
                'ExperimentFileName': experiment_file_name
            }
        
        @staticmethod
        def create_experiment_feedback_message(experiment_id, ready_status=1):
            """创建试验准备反馈消息(0x0002)"""
            # 消息头
            msg_id = 0x0002
            source_plat = 0x00000001  # 本地平台代码
            receive_plat = 0x00000000  # 远端平台代码
            serial_num = int(time.time()) & 0xFFFFFFFF
            create_time = int(time.time() * 1000)  # 毫秒时间戳
            total_packs = 1
            current_index = 1
            data_length = 5  # ExperimentID(4) + ControlReady(1)
            
            # 打包消息头: MsgID(2) + SourcePlatCode(4) + ReceivePlatCode(4) + SerialNum(4) + 
            #           CreateTime(8) + TotalPacks(1) + CurrentIndex(1) + DataLength(2)
            header = struct.pack('<HIIIQBBH', msg_id, source_plat, receive_plat, serial_num,
                               create_time, total_packs, current_index, data_length)
            
            # 打包消息体
            body = struct.pack('<Ib', experiment_id, ready_status)
            
            return header + body

    # 10月17-由嘉伟-udp解包
    def handle_udp_data(self, data, addr):
        """Handle UDP data from client"""
        log_with_timestamp(f'[UDP Client {addr}] Processing received data...')
        try:
            # Parse received situation data
            try:
                message = data.decode('utf-8')
                log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Decoded message: {message[:100]}{"..." if len(message) > 100 else ""}')
                
                # Try to parse JSON format situation data
                try:
                    situation_data = json.loads(message)
                    log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Successfully parsed JSON data')
                    self.process_situation_data(situation_data, addr)
                    
                    # Forward data to remote server
                    self.send_to_remote(situation_data)
                    
                except json.JSONDecodeError as e:
                    log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] JSON decode error: {e}')
                    log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Processing as plain text')
                    
                    # Forward plain text to remote server
                    self.send_to_remote(message)
                    
            except UnicodeDecodeError as e:
                log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Unicode decode error: {e}')
                log_with_timestamp(f'[UDP Client {addr}] [Message #{self.message_count}] Received binary data of {len(data)} bytes')
                
        except Exception as e:
            log_with_timestamp(f'[UDP Client {addr}] Error handling UDP data: {e}')

    def process_situation_data(self, data, client_addr):
        """Process situation data"""
        log_with_timestamp(f'[UDP Client {client_addr}] Processing situation data...')
        if isinstance(data, dict):
            log_with_timestamp(f'[UDP Client {client_addr}] Data is dictionary with {len(data)} keys: {list(data.keys())}')
            
            if 'red_aircraft' in data:
                aircraft_count = len(data["red_aircraft"])
                log_with_timestamp(f'[UDP Client {client_addr}] Red aircraft count: {aircraft_count}')
                
                for i, aircraft in enumerate(data['red_aircraft']):
                    aircraft_id = aircraft.get("id", "Unknown")
                    aircraft_type = aircraft.get("type", "Unknown")
                    longitude = aircraft.get("longitude", 0)
                    latitude = aircraft.get("latitude", 0)
                    altitude = aircraft.get("altitude", 0)
                    speed = aircraft.get("speed", 0)
                    heading = aircraft.get("heading", 0)
                    status = aircraft.get("status", "Unknown")
                    
                    log_with_timestamp(f'[UDP Client {client_addr}] Aircraft #{i+1}: ID={aircraft_id}, Type={aircraft_type}, '
                                     f'Pos=({longitude}, {latitude}), Alt={altitude}, Speed={speed}, '
                                     f'Heading={heading}, Status={status}')
            
            if 'timestamp' in data:
                log_with_timestamp(f'[UDP Client {client_addr}] Data timestamp: {data["timestamp"]}')
                
            if 'blue_aircraft' in data:
                blue_count = len(data["blue_aircraft"])
                log_with_timestamp(f'[UDP Client {client_addr}] Blue aircraft count: {blue_count}')
                
            if 'parameters' in data:
                params = data["parameters"]
                log_with_timestamp(f'[UDP Client {client_addr}] Parameters: {params}')
        else:
            log_with_timestamp(f'[UDP Client {client_addr}] Data content (non-dict): {str(data)[:200]}{"..." if len(str(data)) > 200 else ""}')

    def send_to_remote(self, data):
        """Send data to remote server via UDP"""
        if self.remote_socket:
            try:
                if isinstance(data, dict):
                    json_data = json.dumps(data, ensure_ascii=False)
                    log_with_timestamp(f'Sending JSON data to remote server via UDP: {json_data[:100]}{"..." if len(json_data) > 100 else ""}')
                    self.remote_socket.sendto(json_data.encode('utf-8'), self.remote_address)
                else:
                    log_with_timestamp(f'Sending text data to remote server via UDP: {str(data)[:100]}{"..." if len(str(data)) > 100 else ""}')
                    self.remote_socket.sendto(str(data).encode('utf-8'), self.remote_address)
                log_with_timestamp('Data sent successfully to remote server via UDP')
            except Exception as e:
                log_with_timestamp(f'Failed to send UDP data to remote server: {e}')
        else:
            log_with_timestamp('Cannot send data: no UDP socket created')

    def run(self):
        """Run debugger"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('Starting online debugger with UDP protocol...')
        log_with_timestamp('=' * 50)
        
        # Create UDP socket for remote communication
        if self.connect_to_remote():
            log_with_timestamp('UDP socket for remote communication ready, starting local UDP server...')
            
            # Start local UDP server thread
            server_thread = threading.Thread(target=self.start_local_server)
            server_thread.daemon = True
            server_thread.start()
            log_with_timestamp('Local UDP server thread started')
            
            try:
                log_with_timestamp('UDP debugger running, press Ctrl+C to exit...')
                log_with_timestamp('Monitoring UDP packets and data flow...')
                
                # Print status every 30 seconds
                status_counter = 0
                while self.running:
                    time.sleep(1)
                    status_counter += 1
                    if status_counter % 30 == 0:
                        log_with_timestamp(f'Status: {len(self.client_addresses)} unique UDP clients, {self.message_count} total UDP packets processed')
                        
            except KeyboardInterrupt:
                log_with_timestamp('\nReceived exit signal (Ctrl+C)')
        else:
            log_with_timestamp('Failed to create UDP socket, exiting...')
        
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('Cleaning up UDP resources...')
        self.running = False
        
        if self.remote_socket:
            try:
                self.remote_socket.close()
                log_with_timestamp('Remote UDP socket closed')
            except Exception as e:
                log_with_timestamp(f'Error closing remote UDP socket: {e}')
            
        if self.local_socket:
            try:
                self.local_socket.close()
                log_with_timestamp('Local UDP server closed')
            except Exception as e:
                log_with_timestamp(f'Error closing local UDP server: {e}')
                
        log_with_timestamp(f'Final statistics: {len(self.client_addresses)} unique UDP clients, {self.message_count} UDP packets processed')
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