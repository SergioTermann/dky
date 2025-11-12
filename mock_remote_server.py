#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模拟远端服务器 - 用于本地测试
监听UDP消息并解析显示
"""

import socket
import struct
import time
import datetime
from collections import defaultdict

# 监听配置（模拟远端服务器）
LISTEN_IP = '0.0.0.0'  # 监听所有网卡
LISTEN_PORT = 1007

def log_with_timestamp(message):
    """带时间戳的日志输出"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


class MockRemoteServer:
    """模拟远端服务器"""
    
    def __init__(self, listen_ip=LISTEN_IP, listen_port=LISTEN_PORT):
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.socket = None
        self.running = True
        self.message_count = 0
        self.platform_data = {}  # 存储平台数据
        self.message_stats = defaultdict(int)  # 消息统计
        self.client_address = None  # 记录客户端地址
        
    def parse_message_header(self, data):
        """解析UDP消息头"""
        if len(data) < 26:
            return None
            
        try:
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
        except Exception as e:
            log_with_timestamp(f"解析消息头失败: {e}")
            return None
    
    def parse_platform_status_message(self, data):
        """解析平台状态消息 (0x1001)"""
        if len(data) < 85:  # 26字节消息头 + 108字节消息体
            log_with_timestamp(f"数据长度不足: {len(data)} < 85")
            return None
            
        try:
            # 解析消息体
            offset = 26
            
            # Time (uint64, 8字节)
            msg_time = struct.unpack('<Q', data[offset:offset+8])[0]
            offset += 8
            
            # ID (uint32, 4字节)
            platform_id = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            # Longitude (int32, 4字节, 1e-6度精度)
            longitude_raw = struct.unpack('<i', data[offset:offset+4])[0]
            longitude = longitude_raw / 1000000.0
            offset += 4
            
            # Latitude (int32, 4字节, 1e-6度精度)
            latitude_raw = struct.unpack('<i', data[offset:offset+4])[0]
            latitude = latitude_raw / 1000000.0
            offset += 4
            
            # Height (int32, 4字节, 0.01m精度)
            height_raw = struct.unpack('<i', data[offset:offset+4])[0]
            height = height_raw / 100.0
            offset += 4
            
            # Speed (int16, 2字节, 0.01m/s精度)
            speed_raw = struct.unpack('<h', data[offset:offset+2])[0]
            speed = speed_raw / 100.0
            offset += 2
            
            # Course (int32, 4字节, 0.01度精度)
            course_raw = struct.unpack('<i', data[offset:offset+4])[0]
            course = course_raw / 100.0
            offset += 4
            
            # Roll (int16, 2字节, 0.01度精度)
            roll_raw = struct.unpack('<h', data[offset:offset+2])[0]
            roll = roll_raw / 100.0
            offset += 2
            
            # Pitch (int16, 2字节, 0.01度精度)
            pitch_raw = struct.unpack('<h', data[offset:offset+2])[0]
            pitch = pitch_raw / 100.0
            offset += 2
            
            # Amount (uint8, 1字节)
            amount = struct.unpack('<B', data[offset:offset+1])[0]
            offset += 1
            
            # Kind (int8, 1字节)
            kind = struct.unpack('<b', data[offset:offset+1])[0]
            offset += 1
            
            # Type (int16, 2字节)
            platform_type = struct.unpack('<h', data[offset:offset+2])[0]
            offset += 2
            
            # CommanderID (uint32, 4字节)
            commander_id = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            # FormationID (uint32, 4字节)
            formation_id = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            # Task (uint8, 1字节)
            task = struct.unpack('<B', data[offset:offset+1])[0]
            offset += 1
            
            # EnergyRemain (int8, 1字节)
            energy_remain = struct.unpack('<b', data[offset:offset+1])[0]
            offset += 1
            
            # 其余字段...
            weapon_kind = struct.unpack('<b', data[offset:offset+1])[0]
            offset += 1
            weapon_amount = struct.unpack('<B', data[offset:offset+1])[0]
            offset += 1
            health_state = struct.unpack('<b', data[offset:offset+1])[0]
            
            return {
                'Time': msg_time,
                'ID': platform_id,
                'Longitude': longitude,
                'Latitude': latitude,
                'Height': height,
                'Speed': speed,
                'Course': course,
                'Roll': roll,
                'Pitch': pitch,
                'Amount': amount,
                'Kind': kind,
                'Type': platform_type,
                'CommanderID': commander_id,
                'FormationID': formation_id,
                'Task': task,
                'EnergyRemain': energy_remain,
                'WeaponKind': weapon_kind,
                'WeaponAmount': weapon_amount,
                'HealthState': health_state
            }
        except Exception as e:
            log_with_timestamp(f"解析平台状态消息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def parse_node_registration_message(self, data):
        """解析节点注册消息 (0x0005)"""
        if len(data) < 149:  # 26 + 123
            return None
            
        try:
            offset = 26
            node_type = struct.unpack('<b', data[offset:offset+1])[0]
            offset += 1
            
            node_ip = data[offset:offset+20].rstrip(b'\x00').decode('utf-8', errors='ignore')
            offset += 20
            
            node_port = struct.unpack('<H', data[offset:offset+2])[0]
            offset += 2
            
            node_name = data[offset:offset+100].rstrip(b'\x00').decode('utf-8', errors='ignore')
            
            return {
                'NodeType': node_type,
                'NodeIP': node_ip,
                'NodePort': node_port,
                'NodeName': node_name
            }
        except Exception as e:
            log_with_timestamp(f"解析节点注册消息失败: {e}")
            return None
    
    def parse_control_feedback_message(self, data):
        """解析管控消息结果反馈 (0x0004)"""
        if len(data) < 28:  # 26 + 2
            return None
            
        try:
            offset = 26
            control_type = struct.unpack('<b', data[offset:offset+1])[0]
            offset += 1
            control_feedback = struct.unpack('<b', data[offset:offset+1])[0]
            
            return {
                'ControlType': control_type,
                'ControlFeedback': control_feedback
            }
        except Exception as e:
            log_with_timestamp(f"解析管控反馈消息失败: {e}")
            return None
    
    def display_platform_status(self, platform_data):
        """格式化显示平台状态"""
        log_with_timestamp("=" * 80)
        log_with_timestamp(f"【红方平台状态】ID: {platform_data['ID']}")
        log_with_timestamp(f"  位置: 经度={platform_data['Longitude']:.6f}°, "
                         f"纬度={platform_data['Latitude']:.6f}°, "
                         f"高度={platform_data['Height']:.2f}m")
        log_with_timestamp(f"  运动: 速度={platform_data['Speed']:.2f}m/s, "
                         f"航向={platform_data['Course']:.2f}°")
        log_with_timestamp(f"  姿态: 横滚={platform_data['Roll']:.2f}°, "
                         f"俯仰={platform_data['Pitch']:.2f}°")
        log_with_timestamp(f"  平台: 类型={platform_data['Kind']}, "
                         f"型号={platform_data['Type']}, "
                         f"数量={platform_data['Amount']}")
        log_with_timestamp(f"  指挥: 指控平台={platform_data['CommanderID']}, "
                         f"编队长机={platform_data['FormationID']}")
        log_with_timestamp(f"  状态: 任务={platform_data['Task']}, "
                         f"电量={platform_data['EnergyRemain']}%, "
                         f"健康={platform_data['HealthState']}")
        log_with_timestamp("=" * 80)
    
    def create_control_message(self, control_type):
        """创建试验管控消息(0x0003)"""
        # 消息头
        msg_id = 0x0003
        source_plat = 0x00000000  # 远端平台代码
        receive_plat = 0x00000001  # 本地平台代码
        serial_num = int(time.time()) & 0xFFFFFFFF
        create_time = int(time.time() * 1000)  # 毫秒时间戳
        total_packs = 1
        current_index = 1
        data_length = 1  # ControlType(1字节)
        
        # 打包消息头
        header = struct.pack('<HIIIQBBH', msg_id, source_plat, receive_plat, serial_num,
                           create_time, total_packs, current_index, data_length)
        
        # 打包消息体
        body = struct.pack('<b', control_type)
        
        return header + body
    
    def send_control_message(self, control_type, target_addr):
        """发送管控消息到客户端"""
        if not self.socket or not target_addr:
            return False
        
        try:
            msg = self.create_control_message(control_type)
            self.socket.sendto(msg, target_addr)
            
            control_type_desc = {
                1: "试验开始",
                2: "试验暂停",
                3: "试验恢复",
                4: "试验结束",
                5: "一键返航"
            }.get(control_type, f"未知类型({control_type})")
            
            log_with_timestamp(f"✓ 已发送管控消息: {control_type_desc} -> {target_addr}")
            return True
        except Exception as e:
            log_with_timestamp(f"✗ 发送管控消息失败: {e}")
            return False
    
    def start(self):
        """启动模拟服务器"""
        log_with_timestamp("=" * 80)
        log_with_timestamp("模拟远端服务器启动中...")
        log_with_timestamp("=" * 80)
        
        try:
            # 创建UDP套接字
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.listen_ip, self.listen_port))
            
            log_with_timestamp(f"✓ UDP服务器启动成功")
            log_with_timestamp(f"✓ 监听地址: {self.listen_ip}:{self.listen_port}")
            log_with_timestamp(f"✓ 等待接收消息...")
            log_with_timestamp("=" * 80)
            
            while self.running:
                try:
                    # 接收数据
                    data, addr = self.socket.recvfrom(8192)
                    addr = ('127.0.0.1',10113)
                    self.message_count += 1

                    
                    # 记录客户端地址
                    if self.client_address is None:
                        self.client_address = addr
                        log_with_timestamp(f"✓ 记录客户端地址: {addr}")
                        
                        # 在首次收到消息后，发送试验开始指令
                        log_with_timestamp("-" * 80)
                        log_with_timestamp("自动发送试验管控消息：试验开始")
                        time.sleep(0.5)  # 稍微延迟，确保客户端准备好
                        self.send_control_message(control_type=1, target_addr=addr)
                        log_with_timestamp("-" * 80)
                    
                    # 解析消息头
                    header = self.parse_message_header(data)
                    if not header:
                        log_with_timestamp(f"收到未知格式数据 from {addr}, 长度: {len(data)}")
                        continue
                    
                    msg_id = header['MsgID']
                    self.message_stats[msg_id] += 1
                    # print('!!!')
                    # 根据消息类型解析
                    if msg_id == 0x1001:

                        # 平台状态消息
                        platform_data = self.parse_platform_status_message(data)
                        if platform_data:
                            log_with_timestamp(f"[消息 #{self.message_count}] 平台状态 (0x1001) from {addr}")
                            self.display_platform_status(platform_data)
                            self.platform_data[platform_data['ID']] = platform_data
                        
                    elif msg_id == 0x0005:
                        # 节点注册消息
                        node_data = self.parse_node_registration_message(data)
                        if node_data:
                            log_with_timestamp(f"[消息 #{self.message_count}] 节点注册 (0x0005) from {addr}")
                            log_with_timestamp(f"  节点类型: {node_data['NodeType']}")
                            log_with_timestamp(f"  节点名称: {node_data['NodeName']}")
                            log_with_timestamp(f"  节点地址: {node_data['NodeIP']}:{node_data['NodePort']}")
                        
                    elif msg_id == 0x0004:
                        # 管控反馈消息
                        feedback_data = self.parse_control_feedback_message(data)
                        if feedback_data:
                            log_with_timestamp(f"[消息 #{self.message_count}] 管控反馈 (0x0004) from {addr}")
                            log_with_timestamp(f"  管控类型: {feedback_data['ControlType']}")
                            log_with_timestamp(f"  执行结果: {feedback_data['ControlFeedback']}")
                    
                    else:
                        log_with_timestamp(f"[消息 #{self.message_count}] 未知消息类型 (0x{msg_id:04X}) from {addr}, "
                                         f"数据长度: {len(data)}")
                    
                    # 每10条消息显示统计
                    if self.message_count % 10 == 0:
                        log_with_timestamp("-" * 80)
                        log_with_timestamp(f"📊 统计: 已接收 {self.message_count} 条消息, "
                                         f"平台数: {len(self.platform_data)}")
                        log_with_timestamp(f"消息类型分布: {dict(self.message_stats)}")
                        log_with_timestamp("-" * 80)
                
                except KeyboardInterrupt:
                    log_with_timestamp("\n收到退出信号 (Ctrl+C)")
                    break
                except Exception as e:
                    log_with_timestamp(f"处理消息时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            log_with_timestamp(f"启动服务器失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """清理资源"""
        log_with_timestamp("=" * 80)
        log_with_timestamp("正在关闭模拟服务器...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
                log_with_timestamp("✓ UDP套接字已关闭")
            except Exception as e:
                log_with_timestamp(f"关闭套接字时出错: {e}")
        
        log_with_timestamp(f"📊 最终统计:")
        log_with_timestamp(f"  总消息数: {self.message_count}")
        log_with_timestamp(f"  平台数: {len(self.platform_data)}")
        log_with_timestamp(f"  消息类型分布: {dict(self.message_stats)}")
        log_with_timestamp("=" * 80)


if __name__ == '__main__':
    server = MockRemoteServer()
    try:
        server.start()
    except Exception as e:
        log_with_timestamp(f"程序异常退出: {e}")
        import traceback
        traceback.print_exc()

