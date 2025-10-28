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
import subprocess

# Configuration parameters
# 远端服务器配置（测试模式：使用本地地址）
REMOTE_IP = '127.0.0.1'  # 测试模式：本地模拟服务器 | 生产模式：'180.1.80.242'
REMOTE_PORT = 1001
LOCAL_IP = '127.0.0.1'  # 测试模式：本地地址 | 生产模式：'180.1.80.129'
LOCAL_PORT = 10113
flag = 0

def log_with_timestamp(message):
    """Print message with timestamp"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

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
    def parse_node_registration_message(data):
        """解析试验节点注册消息(0x0006)"""
        if len(data) < 228:  # 消息头26字节 + 消息体202字节 = 228字节
            return None
            
        # NodeType(1) + RegResult(1) + NodeName(100) + Reason(100)
        node_type = struct.unpack('<b', data[26:27])[0]
        reg_result = struct.unpack('<b', data[27:28])[0]
        node_name = data[28:128].rstrip(b'\x00').decode('utf-8', errors='ignore')
        reason = data[128:228].rstrip(b'\x00').decode('utf-8', errors='ignore')

        log_with_timestamp(f'[NodeType] {node_type}')
        log_with_timestamp(f'[reg_result] {reg_result}')
        # log_with_timestamp(f'[node_name] {node_name}')
        # log_with_timestamp(f'[reason] {reason}')
        
        return {
            'NodeType': node_type,
            'RegResult': reg_result,
            'NodeName': node_name,
            'Reason': reason
        }
    
    @staticmethod
    def parse_control_message(data):
        """解析试验管控消息(0x0003)"""
        if len(data) < 27:  # 消息头26字节 + 消息体1字节 = 27字节
            return None
            
        # ControlType(1字节)
        control_type = struct.unpack('<b', data[26:27])[0]
        
        return {
            'ControlType': control_type
        }
    
    @staticmethod
    def create_control_feedback_message(control_type, control_feedback=1):
        """创建管控消息结果(0x0004)"""
        # 消息头
        msg_id = 0x0004
        source_plat = 0x00000001  # 本地平台代码
        receive_plat = 0x00000000  # 远端平台代码
        serial_num = int(time.time()) & 0xFFFFFFFF
        create_time = int(time.time() * 1000)  # 毫秒时间戳
        total_packs = 1
        current_index = 1
        data_length = 2  # ControlType(1) + ControlFeedBack(1)
        
        # 打包消息头: MsgID(2) + SourcePlatCode(4) + ReceivePlatCode(4) + SerialNum(4) + 
        #           CreateTime(8) + TotalPacks(1) + CurrentIndex(1) + DataLength(2)
        header = struct.pack('<HIIIQBBH', msg_id, source_plat, receive_plat, serial_num,
                           create_time, total_packs, current_index, data_length)
        
        # 打包消息体: ControlType(1) + ControlFeedBack(1)
        body = struct.pack('<bb', control_type, control_feedback)
        
        return header + body
    
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

    @staticmethod
    def create_platform_status_message(platform_id=1, longitude=116.0, latitude=39.0, height=1000, 
                                     speed=200, course=90, roll=0, pitch=0, amount=1, kind=1, 
                                     platform_type=11, commander_id=1, formation_id=1, task=0, 
                                     energy_remain=80, weapon_kind=0, weapon_amount=0, health_state=0,
                                     hang_state=0, ir_state=0, laser_state=0, eo_state=0, 
                                     guide_state=0, comm_state=0, gps_state=0, bd_state=0):
        """创建红方无人装备平台与系统状态消息(0x1001)"""
        # 消息头
        msg_id = 0x1001
        source_plat = 0x00000001  # 本地平台代码
        receive_plat = 0x00000000  # 远端平台代码
        serial_num = int(time.time()) & 0xFFFFFFFF
        create_time = int(time.time() * 1000)  # 毫秒时间戳
        total_packs = 1
        current_index = 1
        data_length = 59  # 消息体总长度
        
        # 打包消息头
        header = struct.pack('<HIIIQBBH', msg_id, source_plat, receive_plat, serial_num,
                           create_time, total_packs, current_index, data_length)
        
        # 打包消息体 - 根据表格定义的字段顺序和数据类型
        body = struct.pack('<Q',      # Time (uint64) - 当前时间
                          create_time) + \
               struct.pack('<I',      # ID (uint32) - 平台编号
                          platform_id) + \
               struct.pack('<i',      # Longitude (int32) - 经度，1e-6度精度
                          int(longitude * 1000000)) + \
               struct.pack('<i',      # Latitude (int32) - 纬度，1e-6度精度
                          int(latitude * 1000000)) + \
               struct.pack('<i',      # Height (int32) - 高度，0.01m精度
                          int(height * 100)) + \
               struct.pack('<h',      # Speed (int16) - 速度，0.01m/s精度
                          int(speed * 100)) + \
               struct.pack('<i',      # Course (int32) - 航向，0.01度精度
                          int(course * 100)) + \
               struct.pack('<h',      # Roll (int16) - 横滚，0.01度精度
                          int(roll * 100)) + \
               struct.pack('<h',      # Pitch (int16) - 俯仰，0.01度精度
                          int(pitch * 100)) + \
               struct.pack('<B',      # Amount (uint8) - 编队内架数
                          amount) + \
               struct.pack('<B',      # Kind (int8) - 平台类型
                          kind) + \
               struct.pack('<h',      # Type (int16) - 平台型号
                          platform_type) + \
               struct.pack('<I',      # CommanderID (uint32) - 指控平台编识号
                          commander_id) + \
               struct.pack('<I',      # FormationID (uint32) - 长机编识号
                          formation_id) + \
               struct.pack('<B',      # Task (uint8) - 平台任务
                          task) + \
               struct.pack('<B',      # EnergyRemain (int8) - 剩余电量
                          energy_remain) + \
               struct.pack('<B',      # WeaponKind (int8) - 弹药种类
                          weapon_kind) + \
               struct.pack('<B',      # WeaponAmount (uchar) - 弹药数量
                          weapon_amount) + \
               struct.pack('<B',      # HealthState (int8) - 整机状态
                          health_state) + \
               struct.pack('<B',      # HangState (int8) - 挂点状态
                          hang_state) + \
               struct.pack('<B',      # IRState (int8) - 红外探测器状态
                          ir_state) + \
               struct.pack('<B',      # LaserState (int8) - 激光探测器状态
                          laser_state) + \
               struct.pack('<B',      # EOState (int8) - 可见光探测器状态
                          eo_state) + \
               struct.pack('<B',      # GuideState (int8) - 惯导设备状态
                          guide_state) + \
               struct.pack('<B',      # CommState (int8) - 通信设备状态
                          comm_state) + \
               struct.pack('<B',      # GPSState (int8) - GPS状态
                          gps_state) + \
               struct.pack('<B',      # BDState (int8) - 北斗状态
                          bd_state)
        
        return header + body

    @staticmethod
    def create_node_registration_message(node_type=1, node_name="TestNode", reason=""):
        """创建试验节点接入注册消息(0x0005)"""
        # 消息头
        msg_id = 0x0005
        source_plat = 0x00000001  # 本地平台代码
        receive_plat = 0x00000000  # 远端平台代码
        serial_num = int(time.time()) & 0xFFFFFFFF
        create_time = int(time.time() * 1000)  # 毫秒时间戳
        total_packs = 1
        current_index = 1
        data_length = 123  # NodeType(1) + NodeIP(20) + NodePort(2) + NodeName(100)
        
        # 打包消息头: MsgID(2) + SourcePlatCode(4) + ReceivePlatCode(4) + SerialNum(4) + 
        #           CreateTime(8) + TotalPacks(1) + CurrentIndex(1) + DataLength(2)
        header = struct.pack('<HIIIQBBH', msg_id, source_plat, receive_plat, serial_num,
                           create_time, total_packs, current_index, data_length)
        
        # 打包消息体: NodeType(1) + NodeIP(20) + NodePort(2) + NodeName(100)
        # 根据表格，试验节点接入注册消息不包含RegResult和Reason字段
        
        # 获取本地IP地址，填充到20字节
        node_ip = LOCAL_IP.encode('utf-8')[:19] + b'\x00'
        node_ip_padded = node_ip.ljust(20, b'\x00')
        
        # 节点端口 (int16, 2字节)
        node_port = LOCAL_PORT
        
        # 确保节点名称不超过指定长度，并用null字节填充
        node_name_bytes = node_name.encode('utf-8')[:99] + b'\x00'
        node_name_padded = node_name_bytes.ljust(100, b'\x00')
        
        body = struct.pack('<b', node_type) + node_ip_padded + struct.pack('<H', node_port) + node_name_padded
        
        return header + body


class OnlineDebugger:
    def __init__(self):
        self.running = True
        self.remote_socket = None
        self.local_socket = None
        self.status_socket = None  # 用于接收态势数据的socket
        self.client_count = 0
        self.message_count = 0
        self.remote_address = (REMOTE_IP, REMOTE_PORT)
        self.client_addresses = set()  # Track unique client addresses
        self.status_broadcast_port = 10114  # 接收态势数据的端口
        log_with_timestamp("在线调试器已初始化，使用UDP通信协议")
        log_with_timestamp(f"目标远程服务器: {REMOTE_IP}:{REMOTE_PORT}")
        log_with_timestamp(f"本地监听地址: {LOCAL_IP}:{LOCAL_PORT}")
        log_with_timestamp(f"态势数据接收端口: 127.0.0.1:{self.status_broadcast_port}")

        self.start_flag = False

    def connect_to_remote(self):
        """Create UDP socket for remote communication"""
        log_with_timestamp("正在创建远程通信UDP套接字...")
        try:
            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            log_with_timestamp("UDP套接字创建成功")
            
            # Test connectivity by sending a test message
            test_message = json.dumps({"type": "connection_test", "timestamp": time.time()})
            log_with_timestamp(f"正在测试UDP连接到 {REMOTE_IP}:{REMOTE_PORT}...")
            
            try:
                self.remote_socket.settimeout(5)  # 5 second timeout for test
                # self.remote_socket.sendto(test_message.encode('utf-8'), self.remote_address)
                # log_with_timestamp("测试消息已发送到远程服务器")

                # Try to receive response (optional for UDP)
                try:
                    response, addr = self.remote_socket.recvfrom(1024)
                    log_with_timestamp(f"收到远程服务器响应: {response.decode('utf-8')[:100]}")
                except socket.timeout:
                    log_with_timestamp("远程服务器无响应（UDP协议正常现象）")
                
                self.remote_socket.settimeout(None)  # Remove timeout
                log_with_timestamp(f'UDP连接到远程服务器 {REMOTE_IP}:{REMOTE_PORT} 已建立')
                return True
                
            except Exception as e:
                log_with_timestamp(f'UDP连接测试失败: {e}')
                log_with_timestamp('继续运行（UDP是无连接协议）')
                self.remote_socket.settimeout(None)
                return True  # UDP is connectionless, so we continue anyway
                
        except Exception as e:
            log_with_timestamp(f'创建UDP套接字失败: {e}')
            return False

    def start_local_server(self):
        """Start local UDP server to receive red aircraft situation data"""
        log_with_timestamp("正在启动本地UDP服务器...")
        try:
            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            log_with_timestamp(f"正在绑定UDP套接字到 {LOCAL_IP}:{LOCAL_PORT}...")
            
            self.local_socket.bind((LOCAL_IP, LOCAL_PORT))
            log_with_timestamp(f'本地UDP服务器启动成功，监听地址 {LOCAL_IP}:{LOCAL_PORT}')
            # log_with_timestamp("等待UDP数据包...")
            
            while self.running:
                try:
                    # log_with_timestamp("等待UDP数据...")
                    # Set timeout to allow periodic status checks
                    self.local_socket.settimeout(1.0)
                    
                    try:
                        data, addr = self.local_socket.recvfrom(4096)
                        
                        # Track unique client addresses
                        if addr not in self.client_addresses:
                            self.client_addresses.add(addr)
                            self.client_count += 1
                            log_with_timestamp(f'[客户端 #{self.client_count}] 新UDP客户端来自 {addr}')
                        
                        self.message_count += 1
                        log_with_timestamp(f'[UDP客户端 {addr}] [消息 #{self.message_count}] 接收到 {len(data)} 字节')
                        
                        # Process the received data
                        self.handle_udp_data(data, addr)
                        
                    except socket.timeout:
                        # Timeout is normal, continue loop
                        continue
                        
                except socket.error as e:
                    if self.running:
                        log_with_timestamp(f'接收UDP数据时出错: {e}')
                        
        except Exception as e:
            log_with_timestamp(f'启动本地UDP服务器失败: {e}')

    def handle_udp_data(self, data, addr):
        """Handle UDP data from client"""
        log_with_timestamp(f'[UDP客户端 {addr}] 正在处理接收到的数据...')
        try:

            # 发送红方态势
            # if self.start_flag:
            #     feedback_msg = UDPMessageParser.create_platform_status_message()
            #     self.send_to_remote(feedback_msg)
            
            # 然后尝试解析UDP消息头
            header = UDPMessageParser.parse_message_header(data)
            if header:
                msg_id = header['MsgID']
                log_with_timestamp(f'[UDP客户端 {addr}] 解析消息头成功，消息ID: 0x{msg_id:04X}')
                
                # 如果接收到的是试验准备消息
                if msg_id == 0x0001:
                    log_with_timestamp(f'[UDP客户端 {addr}] 接收到试验准备消息')
                    # 解析试验准备消息
                    prep_msg = UDPMessageParser.parse_experiment_prep_message(data)
                    if prep_msg:
                        log_with_timestamp(f'[UDP客户端 {addr}] 试验ID: {prep_msg["ExperimentID"]}')
                        log_with_timestamp(f'[UDP客户端 {addr}] 试验名称: {prep_msg["ExperimentName"]}')
                        log_with_timestamp(f'[UDP客户端 {addr}] 试验文件: {prep_msg["ExperimentFileName"]}')
                        
                        # 发送试验准备反馈消息
                        feedback_msg = UDPMessageParser.create_experiment_feedback_message(
                            prep_msg["ExperimentID"], ready_status=1)
                        self.send_to_remote(feedback_msg)
                        log_with_timestamp(f'已发送试验准备反馈消息到远端')
                    else:
                        log_with_timestamp(f'[UDP客户端 {addr}] 解析试验准备消息失败')
                
                # 如果接收到的是节点注册消息
                elif msg_id == 0x0006:
                    log_with_timestamp(f'[UDP客户端 {addr}] 接收到节点注册消息')
                    reg_msg = UDPMessageParser.parse_node_registration_message(data)
                    if reg_msg:
                        log_with_timestamp(f'[UDP客户端 {addr}] 节点类型: {reg_msg["NodeType"]}')
                        log_with_timestamp(f'[UDP客户端 {addr}] 注册结果: {reg_msg["RegResult"]}')
                        # log_with_timestamp(f'[UDP客户端 {addr}] 节点名称: {reg_msg["NodeName"]}')
                        # log_with_timestamp(f'[UDP客户端 {addr}] 原因: {reg_msg["Reason"]}')
                    else:
                        log_with_timestamp(f'[UDP客户端 {addr}] 解析节点注册消息失败')
                
                # 如果接收到的是试验管控消息
                elif msg_id == 0x0003:
                    log_with_timestamp(f'[UDP客户端 {addr}] 接收到试验管控消息')
                    control_msg = UDPMessageParser.parse_control_message(data)
                    if control_msg:
                        control_type = control_msg['ControlType']
                        
                        # 解释管控类型
                        control_type_desc = {
                            1: "试验开始",
                            2: "试验暂停",
                            3: "试验恢复",
                            4: "试验结束",
                            5: "一键返航"
                        }.get(control_type, f"未知管控类型({control_type})")
                        
                        log_with_timestamp(f'[UDP客户端 {addr}] 管控类型: {control_type} - {control_type_desc}')
                        
                        # 如果是试验开始指令
                        if control_type == 1:
                            log_with_timestamp('=' * 50)
                            log_with_timestamp('启动仿真')
                            log_with_timestamp('=' * 50)
                            if not self.start_flag:
                                subprocess.Popen([sys.executable, 'task_allocation.py'])
                                self.start_flag = True

                        # 如果是试验结束指令
                        elif control_type == 4:
                            log_with_timestamp('=' * 50)
                            log_with_timestamp('结束仿真')
                            log_with_timestamp('=' * 50)
                            # 重置启动标志，允许下次重新启动
                            self.start_flag = False
                        
                        # 回复管控消息结果
                        feedback_msg = UDPMessageParser.create_control_feedback_message(
                            control_type, control_feedback=1)  # 1=执行成功
                        self.send_to_remote(feedback_msg)
                        log_with_timestamp(f'[UDP客户端 {addr}] 已发送管控消息结果反馈')

        except Exception as e:
            log_with_timestamp(f'[UDP客户端 {addr}] 处理UDP数据时出错: {e}')
            import traceback
            log_with_timestamp(f'[UDP客户端 {addr}] 完整错误跟踪: {traceback.format_exc()}')

    def send_to_remote(self, data):
        """Send data to remote server via UDP"""
        if self.remote_socket:
            try:
                if isinstance(data, dict):
                    json_data = json.dumps(data, ensure_ascii=False)
                    log_with_timestamp(f'正在通过UDP向远程服务器发送JSON数据: {json_data[:100]}{"..." if len(json_data) > 100 else ""}')
                    self.remote_socket.sendto(json_data.encode('utf-8'), self.remote_address)
                else:
                    log_with_timestamp(f'正在通过UDP向远程服务器发送数据')
                    self.remote_socket.sendto(data, self.remote_address)
                log_with_timestamp('数据已成功通过UDP发送到远程服务器')
            except Exception as e:
                log_with_timestamp(f'向远程服务器发送UDP数据失败: {e}')
        else:
            log_with_timestamp('无法发送数据: 未创建UDP套接字')
    
    def start_status_listener(self):
        """启动态势数据监听线程"""
        log_with_timestamp("正在启动态势数据监听器...")
        try:
            # 创建UDP套接字接收态势数据
            self.status_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.status_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.status_socket.bind(('127.0.0.1', self.status_broadcast_port))
            log_with_timestamp(f'态势数据监听器启动成功，监听端口 127.0.0.1:{self.status_broadcast_port}')
            
            while self.running:
                try:
                    # 设置超时，允许周期性检查
                    self.status_socket.settimeout(1.0)
                    
                    try:
                        data, addr = self.status_socket.recvfrom(8192)
                        
                        # 解析JSON数据
                        status_data = json.loads(data.decode('utf-8'))
                        red_aircraft_list = status_data.get('red_aircraft', [])
                        
                        log_with_timestamp(f'收到态势数据: {len(red_aircraft_list)} 架红方飞机')
                        
                        # 为每架红方飞机构造并发送UDP消息
                        for aircraft in red_aircraft_list:
                            # 构造平台状态消息
                            feedback_msg = UDPMessageParser.create_platform_status_message(
                                platform_id=aircraft.get('platform_id', 1),
                                longitude=aircraft.get('longitude', 116.0),
                                latitude=aircraft.get('latitude', 39.0),
                                height=aircraft.get('height', 1000),
                                speed=aircraft.get('speed', 200),
                                course=aircraft.get('course', 90),
                                roll=aircraft.get('roll', 0),
                                pitch=aircraft.get('pitch', 0),
                                amount=1,
                                kind=1,  # 平台类型
                                platform_type=11,  # 平台型号
                                commander_id=1,
                                formation_id=1,
                                task=0,
                                energy_remain=80,
                                weapon_kind=0,
                                weapon_amount=0,
                                health_state=0,
                                hang_state=0,
                                ir_state=0,
                                laser_state=0,
                                eo_state=0,
                                guide_state=0,
                                comm_state=0,
                                gps_state=0,
                                bd_state=0
                            )
                            if self.start_flag:
                                self.send_to_remote(feedback_msg)
                            # if flag == 1:
                            #     # 发送到远端服务器
                            #     self.send_to_remote(feedback_msg)
                            #     log_with_timestamp(f'已发送红方平台状态: ID={aircraft.get("platform_id")} ({aircraft.get("drone_id")})')
                        
                    except socket.timeout:
                        # 超时正常，继续循环
                        continue
                        
                except socket.error as e:
                    if self.running:
                        log_with_timestamp(f'接收态势数据时出错: {e}')
                        
        except Exception as e:
            log_with_timestamp(f'启动态势数据监听器失败: {e}')
            import traceback
            log_with_timestamp(f'完整错误跟踪: {traceback.format_exc()}')

    def run(self):
        """Run debugger"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('正在启动UDP协议在线调试器...')
        log_with_timestamp('=' * 50)

        # Create UDP socket for remote communication
        if self.connect_to_remote():
            log_with_timestamp('远程通信UDP套接字就绪，正在启动本地UDP服务器...')

            # Start local UDP server thread
            server_thread = threading.Thread(target=self.start_local_server)
            server_thread.daemon = True
            server_thread.start()
            log_with_timestamp('本地UDP服务器线程已启动')
            
            # Start status listener thread to receive red aircraft status from task_allocation.py
            status_thread = threading.Thread(target=self.start_status_listener)
            status_thread.daemon = True
            status_thread.start()
            log_with_timestamp('态势数据监听线程已启动')

            # 在连接建立后立即发送节点注册消息
            log_with_timestamp('正在向远程服务器发送节点注册消息...')
            registration_msg = UDPMessageParser.create_node_registration_message(
                node_type=1,  # 北航实装节点
                node_name="OnlineDebugNode",
                reason=""
            )
            self.send_to_remote(registration_msg)
            log_with_timestamp('节点注册消息已发送到远程服务器')


            try:
                log_with_timestamp('UDP调试器正在运行，按Ctrl+C退出...')
                log_with_timestamp('正在监控UDP数据包和数据流...')
                
                # Print status every 30 seconds
                status_counter = 0
                while self.running:
                    time.sleep(1)
                    status_counter += 1
                    if status_counter % 30 == 0:
                        log_with_timestamp(f'状态: {len(self.client_addresses)} 个唯一UDP客户端，已处理 {self.message_count} 个UDP数据包')
                        
            except KeyboardInterrupt:
                log_with_timestamp('\n收到退出信号 (Ctrl+C)')
        else:
            log_with_timestamp('创建UDP套接字失败，正在退出...')
        
        self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        log_with_timestamp('=' * 50)
        log_with_timestamp('正在清理UDP资源...')
        self.running = False
        
        if self.remote_socket:
            try:
                self.remote_socket.close()
                log_with_timestamp('远程UDP套接字已关闭')
            except Exception as e:
                log_with_timestamp(f'关闭远程UDP套接字时出错: {e}')
            
        if self.local_socket:
            try:
                self.local_socket.close()
                log_with_timestamp('本地UDP服务器已关闭')
            except Exception as e:
                log_with_timestamp(f'关闭本地UDP服务器时出错: {e}')
        
        if self.status_socket:
            try:
                self.status_socket.close()
                log_with_timestamp('态势数据监听套接字已关闭')
            except Exception as e:
                log_with_timestamp(f'关闭态势数据监听套接字时出错: {e}')
                
        log_with_timestamp(f'最终统计: {len(self.client_addresses)} 个唯一UDP客户端，已处理 {self.message_count} 个UDP数据包')
        log_with_timestamp('清理完成')
        log_with_timestamp('=' * 50)


if __name__ == '__main__':
    debugger = OnlineDebugger()
    try:
        debugger.run()
    except Exception as e:
        log_with_timestamp(f'程序异常退出: {e}')
        import traceback
        log_with_timestamp('完整错误跟踪:')
        traceback.print_exc()
        debugger.cleanup()