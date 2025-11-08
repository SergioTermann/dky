import numpy as np
from itertools import combinations
from typing import List, Dict, Set, Tuple, Union
from dataclasses import dataclass
import math
import json
import time
import sys
from socket import *
from struct import pack
from threading import Thread
import random
import tkinter as tk
from tkinter import filedialog
import os
import xml.etree.ElementTree as ET


# 1. Define data classes
@dataclass
class DroneAttributes:
    """无人机个体属性"""
    drone_id: str
    drone_type: str  # 'attack' or 'defense'
    mobility: float  # 机动性 (0-1)
    power: float  # 动力 (0-1)
    distance_to_target: float  # 距离目标区域 (km)


@dataclass
class TaskGroup:
    """任务分组数据结构"""
    defense_drones: List[str]
    attack_drones: List[str]
    shapley_estimate: float
    group_id: int


# Tacview Streamer class
class TacviewStreamer:
    """Tacview实时数据流处理类"""
    
    def __init__(self, local_ip='127.0.0.1', local_port=58008):
        self.local_ip = local_ip
        self.local_port = local_port
        self.socket = None
        self.client_socket = None
        self.is_connected = False
        self.is_streaming = False
        
        # Tacview协议数据
        self.handshake_data1 = 'XtraLib.Stream.0\n'
        self.handshake_data2 = 'Tacview.RealTimeTelemetry.0\n'
        self.handshake_data3 = 'alpha_dog_fight\n'
        
        # 数据格式（匹配训练文件格式）
        self.tel_file_header = "FileType=text/acmi/tacview\nFileVersion=2.1\n"
        self.tel_reference_time_format = '0,ReferenceTime=%Y-%m-%dT%H:%M:%SZ\n'
        self.tel_title = '0,Title = test simple aircraft\n'
        
        # 数据日志文件
        self.log_file = None
        self.log_file_path = 'tacview_data_log.txt'
        
    def start_server(self):
        """启动Tacview服务器"""
        try:
            self.socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
            self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # 允许端口重用
            
            # 增加发送缓冲区大小，支持大数据量传输
            self.socket.setsockopt(SOL_SOCKET, SO_SNDBUF, 524288)  # 512KB发送缓冲区
            
            self.socket.bind((self.local_ip, self.local_port))
            self.socket.listen()
            print('\n' + '=' * 70)
            print('【Tacview服务器启动】')
            print(f'  监听地址: {self.local_ip}:{self.local_port}')
            print(f'  发送缓冲区: 512KB (支持大规模飞机)')
            print('  等待Tacview客户端连接... (5秒超时)')
            print('=' * 70)
            
            # 设置超时，避免无限等待
            self.socket.settimeout(5.0)
            
            try:
                # 等待客户端连接
                self.client_socket, addr = self.socket.accept()
                
                # 为客户端连接设置缓冲区和优化参数
                self.client_socket.setsockopt(SOL_SOCKET, SO_SNDBUF, 524288)  # 512KB发送缓冲
                try:
                    # 禁用Nagle算法，减少延迟（立即发送小数据包）
                    import socket as sock_module
                    self.client_socket.setsockopt(sock_module.IPPROTO_TCP, sock_module.TCP_NODELAY, 1)
                except AttributeError:
                    # 如果TCP_NODELAY不可用，跳过
                    pass
                
                print(f'\n✓ Tacview客户端已连接: {addr}')
                print(f'  Socket优化: 512KB缓冲区 + TCP_NODELAY')
                
                # 发送握手数据
                print('\n【步骤1】发送握手数据...')
                self.client_socket.sendall(self.handshake_data1.encode('utf-8'))
                print(f'  > {self.handshake_data1.strip()}')
                self.client_socket.sendall(self.handshake_data2.encode('utf-8'))
                print(f'  > {self.handshake_data2.strip()}')
                self.client_socket.sendall(self.handshake_data3.encode('utf-8'))
                print(f'  > {self.handshake_data3.strip()}')
                self.client_socket.sendall(b'\x00')
                print('  > NULL字节')
                
                # 接收握手响应
                print('\n【步骤2】接收握手响应...')
                data = self.client_socket.recv(1024)
                print(f'  < 握手响应: {data}')
                
                # 发送文件头和参考时间（匹配训练文件格式）
                print('\n【步骤3】发送ACMI文件头...')
                self.client_socket.sendall(self.tel_file_header.encode('utf-8'))
                print(f'  > {self.tel_file_header.strip()}')
                
                current_time = time.strftime(self.tel_reference_time_format, time.gmtime()).encode('utf-8')
                self.client_socket.sendall(current_time)
                print(f'  > {current_time.decode().strip()}')
                
                # 发送标题（匹配训练文件格式）
                self.client_socket.sendall(self.tel_title.encode('utf-8'))
                print(f'  > {self.tel_title.strip()}')
                
                # 打开日志文件，记录发送的数据
                try:
                    self.log_file = open(self.log_file_path, 'w', encoding='utf-8')
                    # 写入文件头信息
                    self.log_file.write('=' * 80 + '\n')
                    self.log_file.write('Tacview数据日志\n')
                    self.log_file.write(f'开始时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
                    self.log_file.write('=' * 80 + '\n\n')
                    self.log_file.write('【文件头】\n')
                    self.log_file.write(self.tel_file_header)
                    self.log_file.write(current_time.decode('utf-8'))
                    self.log_file.write(self.tel_title)
                    self.log_file.write('\n' + '-' * 80 + '\n\n')
                    self.log_file.flush()
                    print(f'  > 数据日志文件: {self.log_file_path}')
                except Exception as e:
                    print(f'  ⚠ 无法创建日志文件: {e}')
                
                self.is_connected = True
                print('\n' + '=' * 70)
                print('✓✓✓ Tacview初始化完成，准备发送飞机数据 ✓✓✓')
                print('=' * 70 + '\n')
                return True
                
            except timeout:
                print('\n' + '!' * 70)
                print('【警告】等待Tacview客户端连接超时')
                print('  提示: 请确保Tacview已打开并连接到 127.0.0.1:58008')
                print('  仿真将继续运行但不显示Tacview')
                print('!' * 70 + '\n')
                self.is_connected = False
                return False
            
        except Exception as e:
            print('\n' + '!' * 70)
            print(f'【错误】启动Tacview服务器失败: {e}')
            import traceback
            traceback.print_exc()
            print('!' * 70 + '\n')
            return False
    
    def send_drone_data(self, drone_id, position, velocity, drone_type, timestamp):
        """发送单架无人机数据到Tacview（不包含时间戳帧头）"""
        if not self.is_connected or not self.client_socket:
            return False
            
        try:
            # 转换坐标系 (x,y,z -> lon,lat,alt)
            if len(position) == 3:
                x, y, z = position
            else:
                x, y = position
                z = 1000 + random.uniform(-100, 100)  # 模拟高度
            
            # 简单的坐标转换 (这里可以根据实际需要调整)
            longitude = (x - 50) * 0.01  # 将x坐标转换为经度
            latitude = (y - 50) * 0.01   # 将y坐标转换为纬度
            altitude = z
            
            # 确保经纬度在有效范围内
            # 经度范围：-180 到 +180
            longitude = max(-180.0, min(180.0, longitude))
            # 纬度范围：-90 到 +90
            latitude = max(-90.0, min(90.0, latitude))
            
            # 姿态角度
            roll = random.uniform(-5, 5)
            pitch = random.uniform(-5, 5)
            
            # 根据速度向量计算航向角 (yaw)
            if velocity and len(velocity) >= 2:
                vx, vy = velocity[0], velocity[1]
                if abs(vx) > 0.001 or abs(vy) > 0.001:  # 避免除零错误
                    # 计算航向角 (北为0度，顺时针为正)
                    # atan2(vx, vy) 给出从北方向顺时针的角度
                    yaw = math.degrees(math.atan2(vx, vy))
                    # 确保角度在0-360度范围内
                    if yaw < 0:
                        yaw += 360
                else:
                    # 如果速度很小，保持之前的航向或使用默认值
                    yaw = 0
            else:
                vx, vy = 0, 0
                yaw = 0
            
            speed = math.sqrt(vx**2 + vy**2)
            
            # 计算马赫数（假设在海平面，音速约340m/s）
            mach = speed / 340.0 if speed > 0 else 0.8
            mach = min(mach, 2.0)  # 限制最大马赫数
            
            # 设置颜色和阵营（参考训练文件格式）
            if drone_type == 'attack':
                color = 'Red'
                coalition = 'Enemies'
                name = 'F-16'
                short_name = f'F-16  {drone_id[1:]}  3.00'  # 格式如 "F-16  1  3.00"
            else:
                color = 'Blue'
                coalition = 'Enemies'  # 蓝方也标记为Enemies（对抗模式）
                name = 'F-16'
                short_name = f'F-16  {drone_id[1:]}  3.00'  # 格式如 "F-16  1  3.00"
            
            # 生成唯一ID - 确保红蓝双方至少各支持100架不重复
            # 攻击型（红方）：1-9999
            # 防御型（蓝方）：10001-19999
            # 这样可以支持每方最多9999架飞机
            if drone_type == 'attack':
                # 红方：从drone_id "A1", "A2", ... 提取数字
                object_id = int(''.join(filter(str.isdigit, drone_id)))
            else:
                # 蓝方：基数10000 + 提取的数字
                object_id = 10000 + int(''.join(filter(str.isdigit, drone_id)))
            
            # 返回格式化的数据行（完全匹配训练文件格式）
            # 格式：ID,T=经度|纬度|高度|roll|pitch|yaw,Type=Air+FixedWing,Coalition=Enemies,Color=Red/Blue,Name=F-16,Mach=0.800,ShortName=...,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10,RadarVerticalBeamwidth=10
            data = (f'{object_id},'
                   f'T={longitude:.7f}|{latitude:.7f}|{altitude:.7f}|{roll:.7f}|{pitch:.7f}|{yaw:.7f},'
                   f'Type=Air+FixedWing,'
                   f'Coalition={coalition},'
                   f'Color={color},'
                   f'Name={name},'
                   f'Mach={mach:.3f},'
                   f'ShortName={short_name},'
                   f'RadarMode=1,'
                   f'RadarRange=2000,'
                   f'RadarHorizontalBeamwidth=10,'
                   f'RadarVerticalBeamwidth=10\n')
            
            return data
            
        except Exception as e:
            print(f"格式化Tacview数据失败: {e}")
            return None
    
    def send_frame_data(self, timestamp, drone_data_list):
        """批量发送一帧的所有无人机数据 - 参考fourty_enemy.py优化"""
        if not self.is_connected or not self.client_socket:
            return False
            
        try:
            drone_count = len(drone_data_list)
            
            # 参考fourty_enemy.py的简洁写法：直接字符串拼接
            message = f'#{timestamp:.2f}\n'  # 时间戳帧头
            
            # 拼接所有飞机数据
            for data_line in drone_data_list:
                if data_line:
                    message += data_line
            
            # 编码并发送
            encoded_data = message.encode('utf-8')
            data_size = len(encoded_data)
            
            # 写入日志文件
            if self.log_file:
                try:
                    self.log_file.write(f'【时刻 {timestamp:.2f}s】 飞机数: {drone_count}  数据大小: {data_size}字节\n')
                    self.log_file.write(message)
                    self.log_file.write('\n')
                    self.log_file.flush()
                except:
                    pass  # 日志写入失败不影响主流程
            
            # 使用 sendall 确保完整发送
            self.client_socket.sendall(encoded_data)
            
            # 统计信息（每20帧打印一次）
            if not hasattr(self, '_frame_counter'):
                self._frame_counter = 0
                self._total_sent = 0
                self._last_print_frame = 0
            
            self._frame_counter += 1
            self._total_sent += data_size
            
            if self._frame_counter - self._last_print_frame >= 20:
                avg_size = self._total_sent / self._frame_counter
                print(f'【Tacview发送】帧 {self._frame_counter} | 飞机: {drone_count} | 本帧: {data_size}B | 平均: {avg_size:.0f}B')
                self._last_print_frame = self._frame_counter
            
            return True
            
        except BrokenPipeError:
            print('\n【错误】Tacview连接已断开（Broken Pipe）')
            self.is_connected = False
            return False
        except Exception as e:
            print('\n' + '!' * 70)
            print(f'【错误】发送Tacview帧数据失败')
            print(f'  错误类型: {type(e).__name__}')
            print(f'  错误信息: {e}')
            print(f'  时间戳: {timestamp}')
            print(f'  飞机数量: {len(drone_data_list)}')
            import traceback
            traceback.print_exc()
            print('!' * 70 + '\n')
            self.is_connected = False  # 标记为断开
            return False
    
    def send_target_area(self, target_area):
        """发送目标区域中心点标记到Tacview（匹配训练文件格式）
        注意：这应该在文件头之后、第一个时间戳帧之前发送"""
        if not self.is_connected or not self.client_socket:
            return False
            
        try:
            x, y = target_area
            
            # 发送中心靶心标记
            longitude = (x - 50) * 0.01
            latitude = (y - 50) * 0.01
            
            # 确保经纬度在有效范围内
            longitude = max(-180.0, min(180.0, longitude))
            latitude = max(-90.0, min(90.0, latitude))
            
            altitude = 0  # 地面目标
            
            object_id = 1000000  # 固定ID（匹配训练文件）
            
            # 格式匹配训练文件：1000000,T=160.123456|24.8976763|0, Type=Ground+Static+Building, Name=Competition, EngagementRange=30000
            # 注意：目标中心点不带时间戳，直接发送
            data = f'{object_id},T={longitude:.7f}|{latitude:.7f}|{altitude:.1f}, Type=Ground+Static+Building, Name=Competition, EngagementRange=30000\n'
            
            self.client_socket.sendall(data.encode('utf-8'))
            
            # 同时写入日志文件
            if self.log_file:
                try:
                    self.log_file.write('【目标中心点】\n')
                    self.log_file.write(data)
                    self.log_file.write('\n')
                    self.log_file.flush()
                except:
                    pass
            
            print(f'  > 目标中心点已发送: {longitude:.7f}, {latitude:.7f}')
            return True
            
        except Exception as e:
            print(f"发送目标区域数据失败: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        self.is_connected = False
        self.is_streaming = False
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        
        # 关闭日志文件
        if self.log_file:
            try:
                self.log_file.write('\n' + '=' * 80 + '\n')
                self.log_file.write(f'结束时间: {time.strftime("%Y-%m-%d %H:%M:%S")}\n')
                self.log_file.write('=' * 80 + '\n')
                self.log_file.close()
                print(f"数据日志已保存: {self.log_file_path}")
            except:
                pass
        
        print("Tacview连接已关闭")


# 2. Task Allocation class
class GameBasedTaskAllocation:
    """基于博弈的任务分配系统 - 解决负载平衡问题"""

    def __init__(self, attack_drones_data: Dict[str, Dict[str, float]],
                 defense_drones_data: Dict[str, Dict[str, float]]):
        self.M = list(attack_drones_data.keys())
        self.N = list(defense_drones_data.keys())
        self.U = self.M + self.N
        self.drone_attributes = self._initialize_drone_attributes(attack_drones_data, defense_drones_data)
        self.shapley_values = {}
        self.task_groups = []
        self.final_allocation_result = None

    def _initialize_drone_attributes(self, attack_data: Dict[str, Dict[str, float]],
                                     defense_data: Dict[str, Dict[str, float]]) -> Dict[str, DroneAttributes]:
        attributes = {}
        for drone_id, data in attack_data.items():
            attributes[drone_id] = DroneAttributes(
                drone_id=drone_id,
                drone_type='attack',
                mobility=data['mobility'],
                power=data['power'],
                distance_to_target=data['distance_to_target']
            )

        for drone_id, data in defense_data.items():
            attributes[drone_id] = DroneAttributes(
                drone_id=drone_id,
                drone_type='defense',
                mobility=data['mobility'],
                power=data['power'],
                distance_to_target=data['distance_to_target']
            )
        return attributes

    def coalition_value_function(self, coalition: Set[str]) -> float:
        """联盟价值函数 - 基于机动性、动力、距离三要素"""
        if not coalition:
            return 0.0

        coalition_list = list(coalition)
        attack_drones = [d for d in coalition_list if d in self.M]
        defense_drones = [d for d in coalition_list if d in self.N]

        total_mobility = sum(self.drone_attributes[d].mobility for d in coalition_list)
        total_power = sum(self.drone_attributes[d].power for d in coalition_list)

        distance_values = []
        for drone in coalition_list:
            attr = self.drone_attributes[drone]
            distance_factor = 1.0 / (1.0 + attr.distance_to_target / 50.0)
            distance_values.append(distance_factor)
        total_distance_value = sum(distance_values)

        base_value = total_mobility * 0.4 + total_power * 0.3 + total_distance_value * 0.3

        synergy_bonus = 0.0
        if attack_drones and defense_drones:
            for attack_drone in attack_drones:
                for defense_drone in defense_drones:
                    attack_attr = self.drone_attributes[attack_drone]
                    defense_attr = self.drone_attributes[defense_drone]
                    mobility_synergy = attack_attr.mobility * defense_attr.power * 0.15
                    power_complement = min(attack_attr.power, defense_attr.power) * 0.1
                    distance_diff = abs(attack_attr.distance_to_target - defense_attr.distance_to_target)
                    distance_synergy = max(0, 0.1 - distance_diff / 100.0)
                    synergy_bonus += mobility_synergy + power_complement + distance_synergy

        balance_bonus = 0.0
        if len(coalition_list) > 1:
            mobility_scores = [self.drone_attributes[d].mobility for d in coalition_list]
            mobility_balance = 1.0 - np.std(mobility_scores)
            balance_bonus = mobility_balance * 0.1

        coordination_cost = 0.0
        if len(coalition_list) > 1:
            distances = [self.drone_attributes[d].distance_to_target for d in coalition_list]
            distance_dispersion = np.std(distances) if len(distances) > 1 else 0
            coordination_cost = distance_dispersion * 0.01 + len(coalition_list) * 0.02

        return max(base_value + synergy_bonus + balance_bonus - coordination_cost, 0.1)

    def marginal_contribution(self, drone: str, coalition: Set[str]) -> float:
        """计算无人机加入联盟时的边际贡献"""
        coalition_with_drone = coalition.union({drone})
        return self.coalition_value_function(coalition_with_drone) - self.coalition_value_function(coalition)

    def calculate_shapley_value(self, drone: str) -> float:
        """计算单个无人机的Shapley值（采样近似方法，适用于大规模飞机）"""
        shapley_value = 0.0
        other_drones = [d for d in self.U if d != drone]
        n = len(self.U)
        
        # 对于大规模飞机（超过20架），使用采样方法
        if n > 20:
            # 采样次数：最多1000次，确保快速计算
            num_samples = min(1000, max(100, n * 5))
            
            for _ in range(num_samples):
                # 随机采样一个联盟大小
                coalition_size = random.randint(0, len(other_drones))
                # 随机选择联盟成员
                if coalition_size > 0:
                    coalition = set(random.sample(other_drones, coalition_size))
                else:
                    coalition = set()
                
                # 计算边际贡献
                marginal_contrib = self.marginal_contribution(drone, coalition)
                shapley_value += marginal_contrib
            
            # 取平均值作为近似Shapley值
            shapley_value /= num_samples
            
        else:
            # 小规模飞机（≤20架）使用精确计算
            for size in range(len(other_drones) + 1):
                for coalition_tuple in combinations(other_drones, size):
                    coalition = set(coalition_tuple)
                    s_size = len(coalition)
                    weight = (math.factorial(s_size) * math.factorial(n - s_size - 1)) / math.factorial(n)
                    marginal_contrib = self.marginal_contribution(drone, coalition)
                    shapley_value += weight * marginal_contrib

        return shapley_value

    def compute_all_shapley_values(self):
        """计算所有无人机的Shapley值"""
        total_drones = len(self.U)
        print(f"\n【计算Shapley值】")
        print(f"  飞机总数: {total_drones} 架")
        
        if total_drones > 20:
            print(f"  使用采样近似方法（大规模优化）")
            print(f"  采样次数: {min(1000, max(100, total_drones * 5))} 次/架")
        else:
            print(f"  使用精确计算方法")
        
        start_time = time.time()
        
        for i, drone in enumerate(self.U):
            self.shapley_values[drone] = self.calculate_shapley_value(drone)
            
            # 每处理10%输出进度
            if (i + 1) % max(1, total_drones // 10) == 0:
                progress = (i + 1) / total_drones * 100
                elapsed = time.time() - start_time
                print(f"  进度: {i+1}/{total_drones} ({progress:.0f}%) | 已用时: {elapsed:.1f}秒")
        
        elapsed = time.time() - start_time
        print(f"  ✓ Shapley值计算完成，耗时: {elapsed:.2f}秒\n")

    def initialize_task_groups(self) -> List[TaskGroup]:
        """初始化任务分组"""
        groups = []
        for i, defense_drone in enumerate(self.N):
            group = TaskGroup(
                defense_drones=[defense_drone],
                attack_drones=[],
                shapley_estimate=self.shapley_values[defense_drone],
                group_id=i + 1
            )
            groups.append(group)
        return groups

    def _calculate_threat_score_for_attack_mode(self, attack_drone: str) -> float:
        """计算攻击模式下攻击无人机的威胁度（提高攻击能力权重）"""
        attr = self.drone_attributes[attack_drone]
        max_shapley = max(self.shapley_values.values()) if self.shapley_values else 1.0
        shapley_weight = self.shapley_values[attack_drone] / max_shapley
        mobility_weight = attr.mobility
        power_weight = attr.power  # 在攻击模式下更重视动力
        distance_weight = 1.0 / (1.0 + attr.distance_to_target / 30.0)
        return shapley_weight * 0.3 + mobility_weight * 0.2 + power_weight * 0.3 + distance_weight * 0.2

    def _calculate_threat_score_for_defense_mode(self, attack_drone: str) -> float:
        """计算防御模式下攻击无人机的威胁度（提高防御能力权重）"""
        attr = self.drone_attributes[attack_drone]
        max_shapley = max(self.shapley_values.values()) if self.shapley_values else 1.0
        shapley_weight = self.shapley_values[attack_drone] / max_shapley
        mobility_weight = attr.mobility
        power_weight = attr.power
        # 在防御模式下，距离更重要（近距离威胁更大）
        distance_weight = 1.0 / (1.0 + attr.distance_to_target / 20.0)  # 更敏感的距离因子
        return shapley_weight * 0.3 + mobility_weight * 0.2 + power_weight * 0.2 + distance_weight * 0.3

    def allocate_attack_drones_for_attack_mode(self, groups: List[TaskGroup]) -> List[TaskGroup]:
        """攻击模式下分配攻击无人机 - 优先考虑攻击能力"""
        remaining_attack_drones = self.M.copy()

        while remaining_attack_drones:
            # 按攻击模式下的威胁度排序
            remaining_attack_drones.sort(key=lambda x: self._calculate_threat_score_for_attack_mode(x), reverse=True)
            attack_drone = remaining_attack_drones.pop(0)
            
            # 选择最佳分组
            best_group = self._select_best_group_for_attack_mode(attack_drone, groups)
            best_group.attack_drones.append(attack_drone)
            self._update_group_shapley_estimate(best_group)

        return groups

    def _select_best_group_for_attack_mode(self, attack_drone: str, groups: List[TaskGroup]) -> TaskGroup:
        """攻击模式下选择最佳分组 - 优先考虑攻击能力"""
        best_group = None
        best_score = -float('inf')
        attack_attr = self.drone_attributes[attack_drone]

        for group in groups:
            # 在攻击模式下，我们更关注攻击能力而不是负载平衡
            current_load = len(group.attack_drones)
            
            # 负载因子（攻击模式下允许更多攻击无人机集中）
            if current_load <= 2:
                load_factor = 1.0
            elif current_load <= 4:
                load_factor = 0.8
            else:
                load_factor = 0.5
                
            # 攻击能力匹配
            attack_capability = sum(self.drone_attributes[d].power for d in group.defense_drones) / 2.0
            
            # 距离匹配度（攻击模式下距离不那么重要）
            if group.attack_drones:
                group_distances = [self.drone_attributes[d].distance_to_target
                                  for d in group.defense_drones + group.attack_drones]
                group_avg_distance = np.mean(group_distances)
            else:
                group_avg_distance = np.mean([self.drone_attributes[d].distance_to_target
                                             for d in group.defense_drones])
                                             
            distance_diff = abs(attack_attr.distance_to_target - group_avg_distance)
            distance_match = 1.0 / (1.0 + distance_diff / 30.0)  # 攻击模式下距离容忍度更高
            
            # 综合评分（攻击模式下更重视攻击能力）
            match_score = (load_factor * 0.4 + attack_capability * 0.4 + distance_match * 0.2)
            
            if match_score > best_score:
                best_score = match_score
                best_group = group
                
        return best_group

    def allocate_attack_drones_for_defense_mode(self, groups: List[TaskGroup]) -> List[TaskGroup]:
        """防御模式下分配攻击无人机 - 优先考虑防御能力"""
        remaining_attack_drones = self.M.copy()

        while remaining_attack_drones:
            # 按防御模式下的威胁度排序
            remaining_attack_drones.sort(key=lambda x: self._calculate_threat_score_for_defense_mode(x), reverse=True)
            attack_drone = remaining_attack_drones.pop(0)
            
            # 选择最佳分组
            best_group = self._select_best_group_for_defense_mode(attack_drone, groups)
            best_group.attack_drones.append(attack_drone)
            self._update_group_shapley_estimate(best_group)

        return groups

    def _select_best_group_for_defense_mode(self, attack_drone: str, groups: List[TaskGroup]) -> TaskGroup:
        """防御模式下选择最佳分组 - 优先考虑防御能力"""
        best_group = None
        best_score = -float('inf')
        attack_attr = self.drone_attributes[attack_drone]

        for group in groups:
            # 在防御模式下，我们更关注均衡分配和防御能力
            current_load = len(group.attack_drones)
            
            # 负载因子（防御模式下更严格的负载平衡）
            if current_load == 0:
                load_factor = 1.0
            elif current_load == 1:
                load_factor = 0.6
            elif current_load == 2:
                load_factor = 0.3
            else:
                load_factor = 0.1
                
            # 防御能力匹配
            defense_capability = sum(self.drone_attributes[d].mobility for d in group.defense_drones) / 2.0
            
            # 距离匹配度（防御模式下距离更重要）
            if group.attack_drones:
                group_distances = [self.drone_attributes[d].distance_to_target
                                  for d in group.defense_drones + group.attack_drones]
                group_avg_distance = np.mean(group_distances)
            else:
                group_avg_distance = np.mean([self.drone_attributes[d].distance_to_target
                                             for d in group.defense_drones])
                                             
            distance_diff = abs(attack_attr.distance_to_target - group_avg_distance)
            distance_match = 1.0 / (1.0 + distance_diff / 15.0)  # 防御模式下距离更敏感
            
            # 综合评分（防御模式下更重视负载平衡和距离）
            match_score = (load_factor * 0.5 + defense_capability * 0.2 + distance_match * 0.3)
            
            if match_score > best_score:
                best_score = match_score
                best_group = group
                
        return best_group

    def _calculate_threat_score(self, attack_drone: str) -> float:
        """计算攻击无人机的威胁度"""
        attr = self.drone_attributes[attack_drone]
        max_shapley = max(self.shapley_values.values()) if self.shapley_values else 1.0
        shapley_weight = self.shapley_values[attack_drone] / max_shapley
        mobility_weight = attr.mobility
        distance_weight = 1.0 / (1.0 + attr.distance_to_target / 30.0)
        return shapley_weight * 0.4 + mobility_weight * 0.3 + distance_weight * 0.3

    def _select_best_group_with_load_balance(self, attack_drone: str, groups: List[TaskGroup]) -> TaskGroup:
        """选择最佳分组 - 重点考虑负载平衡"""
        best_group = None
        best_score = -float('inf')
        attack_attr = self.drone_attributes[attack_drone]

        for group in groups:
            current_load = len(group.attack_drones)

            # 负载平衡因子
            if current_load == 0:
                load_factor = 1.0
            elif current_load == 1:
                load_factor = 0.7
            elif current_load == 2:
                load_factor = 0.4
            else:
                load_factor = 0.1

            # 防御能力匹配
            defense_capability = group.shapley_estimate / 2.0

            # 距离匹配度
            if group.attack_drones:
                group_distances = [self.drone_attributes[d].distance_to_target
                                   for d in group.defense_drones + group.attack_drones]
                group_avg_distance = np.mean(group_distances)
            else:
                group_avg_distance = np.mean([self.drone_attributes[d].distance_to_target
                                              for d in group.defense_drones])

            distance_diff = abs(attack_attr.distance_to_target - group_avg_distance)
            distance_match = 1.0 / (1.0 + distance_diff / 20.0)

            # 综合评分
            match_score = (load_factor * 0.6 + defense_capability * 0.25 + distance_match * 0.15)

            if match_score > best_score:
                best_score = match_score
                best_group = group

        return best_group

    def allocate_attack_drones(self, groups: List[TaskGroup]) -> List[TaskGroup]:
        """分配攻击无人机 - 负载平衡优先"""
        remaining_attack_drones = self.M.copy()

        while remaining_attack_drones:
            remaining_attack_drones.sort(key=lambda x: self._calculate_threat_score(x), reverse=True)
            attack_drone = remaining_attack_drones.pop(0)
            best_group = self._select_best_group_with_load_balance(attack_drone, groups)
            best_group.attack_drones.append(attack_drone)
            self._update_group_shapley_estimate(best_group)

        return groups

    def _update_group_shapley_estimate(self, group: TaskGroup):
        """更新分组的Shapley估计值"""
        total_shapley = sum(self.shapley_values.get(drone, 0) for drone in group.defense_drones + group.attack_drones)
        group.shapley_estimate = total_shapley

    def validate_allocation_balance(self) -> Dict[str, float]:
        """验证分配结果的平衡性"""
        if not self.task_groups:
            return {}

        group_sizes = [len(g.defense_drones) + len(g.attack_drones) for g in self.task_groups]
        attack_loads = [len(g.attack_drones) for g in self.task_groups]

        metrics = {
            'total_groups': len(self.task_groups),
            'avg_group_size': np.mean(group_sizes),
            'group_size_std': np.std(group_sizes),
            'avg_attack_load': np.mean(attack_loads),
            'attack_load_std': np.std(attack_loads),
            'max_group_size': max(group_sizes),
            'min_group_size': min(group_sizes),
            'load_balance_ratio': min(group_sizes) / max(group_sizes) if max(group_sizes) > 0 else 0,
            'groups_with_no_attackers': sum(1 for load in attack_loads if load == 0),
            'max_attack_load': max(attack_loads),
            'min_attack_load': min(attack_loads)
        }

        return metrics

    def rebalance_allocation(self) -> List[TaskGroup]:
        """重新平衡分配结果"""
        ideal_attack_load = len(self.M) / len(self.N) if len(self.N) > 0 else 0

        # 找出过载和空闲的分组
        overloaded_groups = []
        underloaded_groups = []

        for group in self.task_groups:
            attack_count = len(group.attack_drones)
            if attack_count > ideal_attack_load + 0.5:
                overloaded_groups.append((group, attack_count))
            elif attack_count < ideal_attack_load - 0.5:
                underloaded_groups.append((group, attack_count))

        # 重新分配攻击无人机
        moves_made = 0
        max_moves = 20

        # 按过载程度排序
        overloaded_groups.sort(key=lambda x: x[1], reverse=True)
        underloaded_groups.sort(key=lambda x: x[1])

        for overloaded_group, overload_count in overloaded_groups:
            while (len(overloaded_group.attack_drones) > ideal_attack_load + 0.5 and
                   underloaded_groups and moves_made < max_moves):

                # 选择要移动的攻击无人机（优先移动威胁度较低的）
                if len(overloaded_group.attack_drones) > 1:
                    attack_to_move = min(overloaded_group.attack_drones,
                                         key=lambda x: self._calculate_threat_score(x))
                else:
                    break

                # 选择目标分组（负载最轻的）
                target_group, target_load = min(underloaded_groups, key=lambda x: x[1])

                # 执行移动
                overloaded_group.attack_drones.remove(attack_to_move)
                target_group.attack_drones.append(attack_to_move)

                # 更新Shapley估计值
                self._update_group_shapley_estimate(overloaded_group)
                self._update_group_shapley_estimate(target_group)

                moves_made += 1

                # 更新欠载分组列表
                underloaded_groups = [(g, len(g.attack_drones)) for g, _ in underloaded_groups]
                underloaded_groups = [(g, load) for g, load in underloaded_groups
                                      if load < ideal_attack_load - 0.5]

                if not underloaded_groups:
                    break

        return self.task_groups

    def _generate_output_for_grouping_strategy(self) -> Dict:
        """生成输出结果"""
        output = {
            'task_groups': [],
            'shapley_values': self.shapley_values.copy(),
            'drone_attributes': {
                drone_id: {
                    'mobility': attr.mobility,
                    'power': attr.power,
                    'distance_to_target': attr.distance_to_target
                } for drone_id, attr in self.drone_attributes.items()
            },
            'allocation_metadata': {
                'total_drones': len(self.U),
                'attack_drones_count': len(self.M),
                'defense_drones_count': len(self.N),
                'final_groups_count': len(self.task_groups)
            }
        }

        for group in self.task_groups:
            group_info = {
                'group_id': group.group_id,
                'defense_drones': group.defense_drones,
                'attack_drones': group.attack_drones,
                'shapley_estimate': group.shapley_estimate,
                'group_size': len(group.defense_drones) + len(group.attack_drones),
                'attack_load': len(group.attack_drones)
            }

            # 安全计算平均值
            all_drones = group.defense_drones + group.attack_drones
            if all_drones:
                group_info.update({
                    'avg_mobility': np.mean([self.drone_attributes[d].mobility for d in all_drones]),
                    'avg_power': np.mean([self.drone_attributes[d].power for d in all_drones]),
                    'avg_distance': np.mean([self.drone_attributes[d].distance_to_target for d in all_drones])
                })
            else:
                group_info.update({
                    'avg_mobility': 0.0,
                    'avg_power': 0.0,
                    'avg_distance': 0.0
                })

            output['task_groups'].append(group_info)

        return output

    def execute_task_allocation(self, task_mode="attack") -> Dict:
        """执行完整的任务分配流程
        
        Args:
            task_mode: 任务模式，可选值为 "attack"(攻击), "defense"(防御), "confrontation"(对抗)
        """
        print(f"执行任务分配，当前模式: {task_mode}")
        
        # 计算Shapley值
        self.compute_all_shapley_values()

        # 初始化分组
        groups = self.initialize_task_groups()
        
        # 根据不同任务模式选择不同的分配策略
        if task_mode == "attack":
            # 攻击模式：优先考虑攻击能力，提高攻击无人机的权重
            groups = self.allocate_attack_drones_for_attack_mode(groups)
        elif task_mode == "defense":
            # 防御模式：优先考虑防御能力，提高防御无人机的权重
            groups = self.allocate_attack_drones_for_defense_mode(groups)
        elif task_mode == "confrontation":
            # 对抗模式：平衡攻防能力
            groups = self.allocate_attack_drones(groups)  # 使用原有的平衡策略
        else:
            # 默认使用原有策略
            groups = self.allocate_attack_drones(groups)

        # 保存分组结果
        self.task_groups = groups

        # 验证平衡性
        balance_metrics = self.validate_allocation_balance()

        # 如果平衡性较差，进行重新平衡
        if (balance_metrics.get('load_balance_ratio', 0) < 0.6 or
                balance_metrics.get('groups_with_no_attackers', 0) > 1):
            groups = self.rebalance_allocation()
            self.task_groups = groups
            self.validate_allocation_balance()

        # 生成最终结果
        self.final_allocation_result = self._generate_output_for_grouping_strategy()

        return self.final_allocation_result


# 3. Load situation data and execute task allocation
def convert_to_xyz(aircraft):
    """将经纬高坐标转换为xyz坐标"""
    # 地球半径（单位：千米）
    R = 6371.0
    
    # 确保输入的经纬度在有效范围内
    longitude = max(-180.0, min(180.0, aircraft['longitude']))
    latitude = max(-90.0, min(90.0, aircraft['latitude']))
    
    # 将经纬度转换为弧度
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    
    # 计算x,y,z坐标（相对于原点）
    x = R * math.cos(lat) * math.cos(lon)
    y = R * math.cos(lat) * math.sin(lon)
    z = aircraft['altitude']  # 高度直接使用
    
    # 计算速度分量（根据航向和速度）
    heading_rad = math.radians(aircraft['heading'])
    speed = aircraft['speed']
    vx = speed * math.sin(heading_rad)
    vy = speed * math.cos(heading_rad)
    vz = 0  # 假设垂直速度为0
    
    return {'x': x, 'y': y, 'z': z, 'vx': vx, 'vy': vy, 'vz': vz}

def load_xml_situation_data(xml_file):
    """从XML文件加载态势数据"""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    data = {'red_aircraft': [], 'blue_aircraft': [], 'parameters': {}}
    
    # 解析红方飞机
    red_aircraft_elem = root.find('red_aircraft')
    if red_aircraft_elem is not None:
        for aircraft_elem in red_aircraft_elem.findall('aircraft'):
            aircraft = {}
            for child in aircraft_elem:
                if child.tag in ['id']:
                    aircraft[child.tag] = int(child.text)
                elif child.tag in ['longitude', 'latitude', 'altitude', 'speed', 'heading']:
                    aircraft[child.tag] = float(child.text)
                else:
                    aircraft[child.tag] = child.text
            
            # 确保经纬度在有效范围内
            if 'longitude' in aircraft:
                aircraft['longitude'] = max(-180.0, min(180.0, aircraft['longitude']))
            if 'latitude' in aircraft:
                aircraft['latitude'] = max(-90.0, min(90.0, aircraft['latitude']))
            
            data['red_aircraft'].append(aircraft)
    
    # 解析蓝方飞机
    blue_aircraft_elem = root.find('blue_aircraft')
    if blue_aircraft_elem is not None:
        for aircraft_elem in blue_aircraft_elem.findall('aircraft'):
            aircraft = {}
            for child in aircraft_elem:
                if child.tag in ['id']:
                    aircraft[child.tag] = int(child.text)
                elif child.tag in ['longitude', 'latitude', 'altitude', 'speed', 'heading']:
                    aircraft[child.tag] = float(child.text)
                else:
                    aircraft[child.tag] = child.text
            
            # 确保经纬度在有效范围内
            if 'longitude' in aircraft:
                aircraft['longitude'] = max(-180.0, min(180.0, aircraft['longitude']))
            if 'latitude' in aircraft:
                aircraft['latitude'] = max(-90.0, min(90.0, aircraft['latitude']))
            
            data['blue_aircraft'].append(aircraft)
    
    # 解析参数
    params_elem = root.find('parameters')
    if params_elem is not None:
        for child in params_elem:
            if child.tag == 'blue_count':
                data['parameters'][child.tag] = int(child.text)
            else:
                data['parameters'][child.tag] = child.text
    
    return data

def load_situation_data(situation_file):
    """从JSON或XML文件加载态势数据"""
    # 根据文件扩展名选择解析方式
    if situation_file.lower().endswith('.xml'):
        data = load_xml_situation_data(situation_file)
    else:
        # 默认使用JSON解析
        with open(situation_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    
    # 确保JSON数据中的经纬度在有效范围内
    for aircraft in data.get('red_aircraft', []):
        if 'longitude' in aircraft:
            aircraft['longitude'] = max(-180.0, min(180.0, aircraft['longitude']))
        if 'latitude' in aircraft:
            aircraft['latitude'] = max(-90.0, min(90.0, aircraft['latitude']))
    
    for aircraft in data.get('blue_aircraft', []):
        if 'longitude' in aircraft:
            aircraft['longitude'] = max(-180.0, min(180.0, aircraft['longitude']))
        if 'latitude' in aircraft:
            aircraft['latitude'] = max(-90.0, min(90.0, aircraft['latitude']))
    
    # 将红方飞机转换为攻击无人机数据
    attack_drones_data = {}
    attack_initial_positions = {}  # 存储初始位置用于Tacview
    for i, aircraft in enumerate(data.get('red_aircraft', [])):
        # 转换为xyz坐标
        coords = convert_to_xyz(aircraft)
        # 计算到目标的距离
        distance = math.sqrt(coords['x']**2 + coords['y']**2 + coords['z']**2)
        # 将速度转换为机动性和动力
        speed = math.sqrt(coords['vx']**2 + coords['vy']**2 + coords['vz']**2)
        mobility = min(1.0, speed / 1000)  # 假设最大速度为1000
        power = min(1.0, coords['z'] / 10000)  # 假设最大高度为10000
        
        drone_id = f'A{i+1}'
        attack_drones_data[drone_id] = {
            'mobility': mobility,
            'power': power,
            'distance_to_target': distance
        }
        
        # 存储初始位置和速度用于Tacview
        attack_initial_positions[drone_id] = {
            'position': (coords['x'], coords['y'], coords['z']),
            'velocity': (coords['vx'], coords['vy'], coords['vz']),
            'type': 'attack'
        }
    
    # 将蓝方飞机转换为防御无人机数据
    defense_drones_data = {}
    defense_initial_positions = {}  # 存储初始位置用于Tacview
    for i, aircraft in enumerate(data.get('blue_aircraft', [])):
        # 转换为xyz坐标
        coords = convert_to_xyz(aircraft)
        # 计算到目标的距离
        distance = math.sqrt(coords['x']**2 + coords['y']**2 + coords['z']**2)
        # 将速度转换为机动性和动力
        speed = math.sqrt(coords['vx']**2 + coords['vy']**2 + coords['vz']**2)
        mobility = min(1.0, speed / 1000)  # 假设最大速度为1000
        power = min(1.0, coords['z'] / 10000)  # 假设最大高度为10000
        
        drone_id = f'D{i+1}'
        defense_drones_data[drone_id] = {
            'mobility': mobility,
            'power': power,
            'distance_to_target': distance
        }
        
        # 存储初始位置和速度用于Tacview
        defense_initial_positions[drone_id] = {
            'position': (coords['x'], coords['y'], coords['z']),
            'velocity': (coords['vx'], coords['vy'], coords['vz']),
            'type': 'defense'
        }
    
    # 合并初始位置数据
    initial_positions = {**attack_initial_positions, **defense_initial_positions}
    
    return attack_drones_data, defense_drones_data, initial_positions


def execute_task_allocation(json_file):
    """执行任务分配"""
    # 从JSON文件加载数据
    attack_drones_data, defense_drones_data, initial_positions = load_situation_data(json_file)
    
    # 检查是否存在控制文件并读取任务模式
    task_mode = "attack"  # 默认为攻击模式
    try:
        with open('simulation_control.json', 'r', encoding='utf-8') as f:
            control_data = json.load(f)
            if 'blue_task_mode' in control_data:
                task_mode = control_data['blue_task_mode']
                print(f"当前蓝方任务模式: {task_mode}")
    except Exception as e:
        print(f"读取控制文件失败，使用默认任务模式: {e}")
    
    # 创建任务分配系统
    allocator = GameBasedTaskAllocation(attack_drones_data, defense_drones_data)
    
    # 根据任务模式选择不同的策略
    allocation_result = allocator.execute_task_allocation(task_mode)
    
    # 添加初始位置信息到结果中
    allocation_result['initial_positions'] = initial_positions
    allocation_result['task_mode'] = task_mode  # 在结果中也记录任务模式
    
    return allocation_result


# 4. Simulation class
class DroneSimulation:
    """Simulates drone movements and streams to Tacview"""

    def __init__(self, allocation_result, target_area=(80, 80), area_size=100, 
                 enable_status_broadcast=True, status_broadcast_port=10114,
                 control_file_path='simulation_control.json'):
        self.allocation_result = allocation_result
        self.target_area = target_area
        self.area_size = area_size
        self.drone_positions = {}
        self.drone_velocities = {}
        self.drone_accelerations = {}  # 加速度
        self.drone_headings = {}  # 航向角
        self.drone_angular_velocities = {}  # 角速度
        
        # 飞行动力学参数
        self.max_speed = 15.0  # 最大速度 (km/h 转换为仿真单位)
        self.max_acceleration = 8.0  # 最大加速度
        self.max_angular_velocity = 45.0  # 最大角速度 (度/秒)
        self.smoothing_factor = 0.15  # 平滑因子 (0-1, 越小越平滑)
        
        # 态势广播设置
        self.enable_status_broadcast = enable_status_broadcast
        self.status_broadcast_port = status_broadcast_port
        self.status_socket = None
        
        # 推演控制参数
        self.control_file_path = control_file_path  # 使用传入的控制文件路径
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.last_control_check_time = 0
        self.control_check_interval = 0.5  # 每0.5秒检查一次控制文件
        
        print(f"  控制文件路径: {self.control_file_path}")
        
        # 初始化态势广播套接字
        if self.enable_status_broadcast:
            self._init_status_broadcast()
        
        # Tacview集成
        self.tacview_streamer = TacviewStreamer()
        # 在单独线程中启动Tacview服务器
        self.tacview_thread = Thread(target=self._start_tacview_server, daemon=True)
        self.tacview_thread.start()
        time.sleep(1)  # 等待服务器启动
    
    def _start_tacview_server(self):
        """在单独线程中启动Tacview服务器"""
        success = self.tacview_streamer.start_server()
        if success:
            print("Tacview服务器启动成功，可以连接Tacview客户端到 127.0.0.1:58008")
        else:
            print("Tacview服务器启动失败")
    
    def _read_control_file(self):
        """读取控制文件更新推演状态"""
        try:
            if not os.path.exists(self.control_file_path):
                return
            
            with open(self.control_file_path, 'r', encoding='utf-8') as f:
                control_data = json.load(f)
            
            old_paused = self.is_paused
            old_speed = self.speed_multiplier
            
            self.is_paused = control_data.get('paused', False)
            self.speed_multiplier = control_data.get('speed_multiplier', 1.0)
            
            # 检测状态变化并打印
            if old_paused != self.is_paused:
                if self.is_paused:
                    print('\n' + '=' * 70)
                    print('⏸️  【推演已暂停】')
                    print('=' * 70 + '\n')
                else:
                    print('\n' + '=' * 70)
                    print('▶️  【推演已继续】')
                    print('=' * 70 + '\n')
            
            if old_speed != self.speed_multiplier and not self.is_paused:
                print(f'\n⚡ 推演倍速已调整: {old_speed}x → {self.speed_multiplier}x\n')
                
        except Exception as e:
            # 读取控制文件失败时使用默认值
            pass
    
    def _init_status_broadcast(self):
        """初始化态势广播UDP套接字"""
        try:
            self.status_socket = socket(AF_INET, SOCK_DGRAM)
            print(f"态势广播已初始化，目标端口: 127.0.0.1:{self.status_broadcast_port}")
        except Exception as e:
            print(f"初始化态势广播套接字失败: {e}")
            self.enable_status_broadcast = False
    
    def _broadcast_status(self):
        """广播当前红方和蓝方态势数据到本地UDP端口"""
        if not self.enable_status_broadcast or not self.status_socket:
            return
        
        try:
            # 构造红方态势数据
            red_aircraft_list = []

            # 构造蓝方目标态势数据（使用实际的防御型无人机）
            blue_targets_list = []
            
            for drone_id in self.drone_positions:
                # 获取无人机的类型（攻击或防御）
                drone_type = self.allocation_result['initial_positions'][drone_id]['type']
                
                # 红方
                if drone_type == 'attack':
                    position = self.drone_positions[drone_id]
                    velocity = self.drone_velocities[drone_id]
                    heading = self.drone_headings.get(drone_id, 0)
                    
                    # 计算速度大小（m/s）
                    speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
                    
                    # 提取平台ID（从 "A1" 提取数字）
                    platform_id = int(''.join(filter(str.isdigit, drone_id)))
                    
                    # 构造飞机数据
                    aircraft_data = {
                        'platform_id': platform_id,
                        'longitude': position[0] / 1000.0,  # 转换为合适的坐标
                        'latitude': position[1] / 1000.0,
                        'height': position[2] if len(position) > 2 else 1000,  # 高度（米）
                        'speed': speed,  # 速度（m/s）
                        'course': heading,  # 航向（度）
                        'roll': 0,
                        'pitch': 0,
                        'drone_id': drone_id
                    }
                    red_aircraft_list.append(aircraft_data)

                # 蓝方目标
                if drone_type == 'defense':
                    position = self.drone_positions[drone_id]
                    velocity = self.drone_velocities[drone_id]
                    heading = self.drone_headings.get(drone_id, 0)
                    
                    # 计算速度大小（m/s）
                    speed = math.sqrt(velocity[0]**2 + velocity[1]**2)
                    
                    # 提取目标ID（从 "D1" 提取数字）
                    target_id = int(''.join(filter(str.isdigit, drone_id)))
                    
                    # 构造目标数据
                    target_data = {
                        'target_id': target_id,
                        'longitude': position[0] / 1000.0,  # 转换为合适的坐标
                        'latitude': position[1] / 1000.0,
                        'height': position[2] if len(position) > 2 else 1000,  # 高度（米）
                        'speed': speed,  # 速度（m/s）
                        'course': heading,  # 航向（度）
                        'roll': 0,
                        'pitch': 0,
                        'target_kind': 5,  # 目标类型：5-无人机
                        'drone_id': drone_id
                    }
                    blue_targets_list.append(target_data)
            
         
            # 发送数据到本地UDP端口
            data = json.dumps({
                'timestamp': time.time(),
                'red_aircraft': red_aircraft_list,
                'blue_targets': blue_targets_list
            }, ensure_ascii=False)
            
            self.status_socket.sendto(
                data.encode('utf-8'),
                ('127.0.0.1', self.status_broadcast_port)
            )
                
        except Exception as e:
            # 静默失败，不影响主仿真
            pass

    def initialize_positions(self):
        """Initialize drone positions based on their distance to target"""
        # Extract drone attributes
        drone_attrs = self.allocation_result['drone_attributes']

        for drone_id, attrs in drone_attrs.items():
            # Convert distance and random angle to x,y coordinates
            distance = attrs['distance_to_target']
            angle = np.random.uniform(0, 2 * np.pi)

            # Position relative to target area
            x = self.target_area[0] + distance * np.cos(angle)
            y = self.target_area[1] + distance * np.sin(angle)

            # Ensure within boundaries
            x = np.clip(x, 0, self.area_size)
            y = np.clip(y, 0, self.area_size)

            self.drone_positions[drone_id] = (x, y)
            self.drone_velocities[drone_id] = (0, 0)  # 初始速度为0
            self.drone_accelerations[drone_id] = (0, 0)  # 初始加速度为0
            self.drone_headings[drone_id] = np.degrees(angle)  # 初始航向角指向目标
            self.drone_angular_velocities[drone_id] = 0  # 初始角速度为0

    def update_positions(self, steps=100):
        """Simulate smooth movement of drones with realistic flight dynamics"""
        dt = 0.1  # 时间步长 (秒)
        max_step_time = 0  # 记录最大单步运行时间
        actual_step = 0  # 实际执行的步数（不包含暂停时的步数）
        
        # Tacview时间戳：从0.0开始，每步增加0.01
        tacview_timestamp = 0.0
        tacview_time_step = 0.01  # 匹配训练文件格式
        
        step = 0
        while step < steps:
            step_start_time = time.time()  # 记录单步开始时间
            
            # 定期检查控制文件
            current_time = time.time()
            if current_time - self.last_control_check_time >= self.control_check_interval:
                self._read_control_file()
                self.last_control_check_time = current_time
            
            # 如果暂停，则跳过计算和Tacview发送，只等待
            if self.is_paused:
                time.sleep(0.1)  # 暂停时仍然休眠，避免CPU占用
                continue  # 跳过本帧的所有计算和发送（不增加step）
            
            # 推演未暂停，增加实际步数和Tacview时间戳
            actual_step += 1
            step += 1
            tacview_timestamp += tacview_time_step  # 时间戳递增0.01
            
            # Calculate group centers
            group_centers = {}
            for group in self.allocation_result['task_groups']:
                all_drones = group['defense_drones'] + group['attack_drones']
                if not all_drones:
                    continue

                positions = [self.drone_positions[d] for d in all_drones]
                x_center = np.mean([p[0] for p in positions])
                y_center = np.mean([p[1] for p in positions])
                group_centers[group['group_id']] = (x_center, y_center)

            # Update positions with smooth flight dynamics
            for group in self.allocation_result['task_groups']:
                group_id = group['group_id']
                all_drones = group['defense_drones'] + group['attack_drones']

                # Skip empty groups
                if not all_drones:
                    continue

                for drone_id in all_drones:
                    drone_type = 'attack' if drone_id in group['attack_drones'] else 'defense'
                    
                    # 获取当前状态
                    x, y = self.drone_positions[drone_id]
                    vx, vy = self.drone_velocities[drone_id]
                    ax, ay = self.drone_accelerations[drone_id]
                    current_heading = self.drone_headings[drone_id]
                    angular_velocity = self.drone_angular_velocities[drone_id]
                    
                    # 计算期望方向
                    # 目标方向
                    target_dx = self.target_area[0] - x
                    target_dy = self.target_area[1] - y
                    target_distance = math.sqrt(target_dx**2 + target_dy**2)
                    
                    if target_distance > 0.1:
                        target_direction = math.degrees(math.atan2(target_dx, target_dy))
                    else:
                        target_direction = current_heading
                    
                    # 编队方向 (如果有编队中心)
                    formation_weight = 0.3
                    if group_id in group_centers:
                        gx, gy = group_centers[group_id]
                        formation_dx = gx - x
                        formation_dy = gy - y
                        formation_distance = math.sqrt(formation_dx**2 + formation_dy**2)
                        
                        if formation_distance > 5.0:  # 只有距离编队中心较远时才考虑编队
                            formation_direction = math.degrees(math.atan2(formation_dx, formation_dy))
                            # 混合目标方向和编队方向
                            target_direction = (target_direction * (1 - formation_weight) + 
                                              formation_direction * formation_weight)
                    
                    # 计算航向角变化 (平滑转向)
                    heading_diff = target_direction - current_heading
                    # 处理角度跨越问题
                    if heading_diff > 180:
                        heading_diff -= 360
                    elif heading_diff < -180:
                        heading_diff += 360
                    
                    # 限制角速度
                    max_angular_accel = 60.0  # 最大角加速度 (度/秒²)
                    desired_angular_velocity = np.clip(heading_diff * 2.0, -self.max_angular_velocity, self.max_angular_velocity)
                    angular_accel = np.clip(desired_angular_velocity - angular_velocity, -max_angular_accel, max_angular_accel)
                    
                    # 更新角速度和航向
                    angular_velocity += angular_accel * dt
                    angular_velocity = np.clip(angular_velocity, -self.max_angular_velocity, self.max_angular_velocity)
                    current_heading += angular_velocity * dt
                    
                    # 确保航向角在0-360度范围内
                    if current_heading < 0:
                        current_heading += 360
                    elif current_heading >= 360:
                        current_heading -= 360
                    
                    # 计算期望速度 (基于当前航向)
                    heading_rad = math.radians(current_heading)
                    
                    # 根据无人机类型设置不同的速度
                    if drone_type == 'attack':
                        desired_speed = self.max_speed * 0.8  # 攻击无人机速度较快
                    else:
                        desired_speed = self.max_speed * 0.6  # 防御无人机速度较慢
                    
                    # 根据距离目标的远近调整速度
                    if target_distance < 10:
                        desired_speed *= 0.5  # 接近目标时减速
                    
                    desired_vx = desired_speed * math.sin(heading_rad)
                    desired_vy = desired_speed * math.cos(heading_rad)
                    
                    # 计算加速度 (平滑加速)
                    accel_x = (desired_vx - vx) * 2.0  # 加速度系数
                    accel_y = (desired_vy - vy) * 2.0
                    
                    # 限制加速度
                    accel_magnitude = math.sqrt(accel_x**2 + accel_y**2)
                    if accel_magnitude > self.max_acceleration:
                        accel_x = accel_x / accel_magnitude * self.max_acceleration
                        accel_y = accel_y / accel_magnitude * self.max_acceleration
                    
                    # 更新速度 (考虑惯性)
                    vx = vx * self.smoothing_factor + (vx + accel_x * dt) * (1 - self.smoothing_factor)
                    vy = vy * self.smoothing_factor + (vy + accel_y * dt) * (1 - self.smoothing_factor)
                    
                    # 限制速度
                    speed = math.sqrt(vx**2 + vy**2)
                    if speed > self.max_speed:
                        vx = vx / speed * self.max_speed
                        vy = vy / speed * self.max_speed
                    
                    # 更新位置
                    new_x = x + vx * dt
                    new_y = y + vy * dt
                    
                    # 边界处理 (反弹效果)
                    if new_x <= 0 or new_x >= self.area_size:
                        vx = -vx * 0.8  # 反弹并减速
                        new_x = np.clip(new_x, 0, self.area_size)
                    if new_y <= 0 or new_y >= self.area_size:
                        vy = -vy * 0.8  # 反弹并减速
                        new_y = np.clip(new_y, 0, self.area_size)
                    
                    # 更新所有状态
                    self.drone_positions[drone_id] = (new_x, new_y)
                    self.drone_velocities[drone_id] = (vx, vy)
                    self.drone_accelerations[drone_id] = (accel_x, accel_y)
                    self.drone_headings[drone_id] = current_heading
                    self.drone_angular_velocities[drone_id] = angular_velocity

            # 批量发送Tacview数据（每帧统一发送所有飞机）
            if self.tacview_streamer and self.tacview_streamer.is_connected:
                try:
                    # 使用递增的Tacview时间戳（从0.01开始，每步0.01）
                    
                    # 使用列表推导式高效收集数据
                    drone_data_list = []
                    
                    # 按顺序收集：先红方，再蓝方（保持一致性）
                    for drone_id in sorted(self.drone_positions.keys()):
                        drone_x, drone_y = self.drone_positions[drone_id]
                        vx, vy = self.drone_velocities.get(drone_id, (0, 0))
                        
                        # 确定无人机类型
                        drone_type = 'attack' if drone_id.startswith('A') else 'defense'
                        
                        # 转换为Tacview坐标系 (经纬度和高度)
                        position = (drone_x, drone_y, 1000 + np.random.uniform(-50, 50))
                        velocity = (vx * 10, vy * 10, 0)
                        
                        # 格式化数据行（时间戳用于计算，但不包含在单行数据中）
                        data_line = self.tacview_streamer.send_drone_data(
                            drone_id, position, velocity, drone_type, tacview_timestamp
                        )
                        if data_line:
                            drone_data_list.append(data_line)
                    
                    # 第一帧时打印数据示例
                    if actual_step == 1 and drone_data_list:
                        print('\n' + '=' * 70)
                        print('【第一帧数据示例】统一时刻发送所有飞机')
                        print(f'  时间戳: #{tacview_timestamp:.2f}')
                        print(f'  飞机总数: {len(drone_data_list)} 架')
                        print(f'  数据大小: {sum(len(line.encode()) for line in drone_data_list)} 字节')
                        print('  前3架飞机数据:')
                        for i, line in enumerate(drone_data_list[:3]):
                            print(f'    [{i+1}] {line.strip()}')
                        if len(drone_data_list) > 3:
                            print(f'    ... 还有 {len(drone_data_list)-3} 架飞机')
                        print('=' * 70 + '\n')
                    
                    # 统一时刻批量发送整帧数据（一次性发送）
                    if drone_data_list:
                        success = self.tacview_streamer.send_frame_data(tacview_timestamp, drone_data_list)
                        if not success:
                            print('【警告】Tacview发送失败，连接可能已断开')
                        
                except Exception as e:
                    # 捕获异常但继续仿真
                    if actual_step <= 5:  # 只在前5帧报告错误
                        print(f'【错误】Tacview数据发送异常: {e}')
                    pass

            # 每50步输出一次进度（已禁用，避免日志过多）
            # if step % 50 == 0:
            #     print(f"仿真进度: {step}/{steps} 步 ({step/steps*100:.1f}%)")
            
            # 广播红方态势数据（每10步广播一次，减少数据量）
            # if step % 10 == 0:
            self._broadcast_status()

            # 计算单步运行时间（不包括sleep延迟）
            step_end_time = time.time()
            step_elapsed = step_end_time - step_start_time
            if step_elapsed > max_step_time:
                max_step_time = step_elapsed

            # 根据速度倍数调整间隔时间
            # 基础间隔0.1秒，速度越快间隔越短
            base_interval = 0.1
            adjusted_interval = base_interval / self.speed_multiplier
            
            # 显示进度（每50帧显示一次，包含速度信息）
            if actual_step % 50 == 0:
                speed_indicator = f"[{self.speed_multiplier}x]"
                progress_pct = (actual_step / steps * 100) if steps > 0 else 0
                print(f"  仿真进度: {actual_step}/{steps} 步 ({progress_pct:.1f}%) {speed_indicator}")
            
            time.sleep(adjusted_interval)  # 根据倍速调整间隔
        
        # 输出仿真统计
        print(f"\n推演统计:")
        print(f"  目标步数: {steps}")
        print(f"  实际执行步数: {actual_step}")
        print(f"  最大单步时间: {max_step_time*1000:.2f} 毫秒 ({max_step_time:.4f} 秒)")
        if actual_step < steps:
            print(f"  提示: 由于暂停，未完成所有步数")

    def calculate_performance_metrics(self):
        """Calculate performance metrics for the allocation"""
        metrics = {
            'avg_distance_to_target': 0,
            'group_cohesion': {},
            'coverage': {}
        }

        # Calculate average distance to target
        total_distance = 0
        for drone_id, position in self.drone_positions.items():
            distance = np.sqrt((position[0] - self.target_area[0]) ** 2 +
                               (position[1] - self.target_area[1]) ** 2)
            total_distance += distance

        metrics['avg_distance_to_target'] = total_distance / len(self.drone_positions)

        # Calculate group cohesion (average distance between group members)
        for group in self.allocation_result['task_groups']:
            all_drones = group['defense_drones'] + group['attack_drones']
            if len(all_drones) <= 1:
                metrics['group_cohesion'][group['group_id']] = 0
                continue

            total_internal_dist = 0
            pair_count = 0

            for i, drone1 in enumerate(all_drones):
                for drone2 in all_drones[i + 1:]:
                    pos1 = self.drone_positions[drone1]
                    pos2 = self.drone_positions[drone2]
                    dist = np.sqrt((pos1[0] - pos2[0]) ** 2 + (pos1[1] - pos2[1]) ** 2)
                    total_internal_dist += dist
                    pair_count += 1

            if pair_count > 0:
                metrics['group_cohesion'][group['group_id']] = total_internal_dist / pair_count
            else:
                metrics['group_cohesion'][group['group_id']] = 0

        return metrics

    def run_simulation(self, steps=100):
        """Run the full simulation with pause/resume support"""
        self.initialize_positions()
        print("开始无人机仿真...")
        
        # 统计飞机数量
        total_drones = len(self.drone_positions)
        attack_drones = sum(1 for d in self.drone_positions.keys() if d.startswith('A'))
        defense_drones = total_drones - attack_drones
        print(f"  红方(攻击)飞机: {attack_drones} 架")
        print(f"  蓝方(防御)飞机: {defense_drones} 架")
        print(f"  总计: {total_drones} 架")
        
        # 读取初始控制状态
        self._read_control_file()
        print(f"  初始状态: {'暂停' if self.is_paused else '运行'} | 倍速: {self.speed_multiplier}x")
        
        # 在Tacview中显示目标区域中心点（在第一帧之前发送）
        if self.tacview_streamer and self.tacview_streamer.is_connected:
            self.tacview_streamer.send_target_area(self.target_area)
            print(f"  Tacview数据流已启动，使用批量发送模式（支持大规模飞机）")
        
        print(f"\n提示: 可通过界面的暂停/继续按钮和倍速选择器实时控制推演\n")
        
        self.update_positions(steps)
        metrics = self.calculate_performance_metrics()

        print("\n仿真性能指标:")
        print(f"到目标的平均距离: {metrics['avg_distance_to_target']:.2f} km")
        print("\n组内聚合度 (成员间平均距离):")
        for group_id, cohesion in metrics['group_cohesion'].items():
            print(f"组 {group_id}: {cohesion:.2f} km")

        print("\n仿真完成！")
        
        # 关闭Tacview连接
        try:
            if self.tacview_streamer:
                self.tacview_streamer.close()
            # 等待线程结束
            if hasattr(self, 'tacview_thread') and self.tacview_thread.is_alive():
                self.tacview_thread.join(timeout=1)
        except Exception as e:
            # 忽略关闭时的错误
            pass


# 5. Main execution
def select_json_file():
    """使用文件对话框选择态势文件（JSON或XML）"""
    # 创建一个隐藏的根窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 打开文件选择对话框
    file_path = filedialog.askopenfilename(
        title="选择态势文件",
        filetypes=[
            ("支持的文件", "*.json;*.xml"),
            ("JSON文件", "*.json"),
            ("XML文件", "*.xml"),
            ("所有文件", "*.*")
        ],
        initialdir=os.getcwd()  # 默认打开当前目录
    )
    
    # 销毁根窗口
    root.destroy()
    
    return file_path


if __name__ == "__main__":
    print('\n' + '=' * 70)
    print('   动态场景生成平台 - 任务分配与推演系统')
    print('=' * 70 + '\n')
    
    # 检查命令行参数
    situation_file = None
    control_file = 'simulation_control.json'  # 默认控制文件路径
    
    if len(sys.argv) > 1:
        situation_file = sys.argv[1]
        print(f"✓ 使用指定的态势文件: {situation_file}")
        
        # 如果提供了第二个参数，作为控制文件路径
        if len(sys.argv) > 2:
            control_file = sys.argv[2]
            print(f"✓ 使用指定的控制文件: {control_file}")
    else:
        # 弹出文件选择对话框
        print("请选择态势文件（JSON或XML）...")
        situation_file = select_json_file()
        
        if not situation_file:
            print("【提示】未选择文件，程序退出。")
            sys.exit(0)
        
        print(f"✓ 选择的态势文件: {situation_file}")
    
    # 检查文件是否存在
    import os
    if not os.path.exists(situation_file):
        print(f"\n【错误】找不到态势文件: {situation_file}")
        sys.exit(1)
    
    try:
        print('\n' + '-' * 70)
        print('【步骤1】执行任务分配...')
        print('-' * 70)
        
        # 执行任务分配
        allocation_result = execute_task_allocation(situation_file)
        
        # 保存结果到JSON文件
        with open('task_allocation_output.json', 'w', encoding='utf-8') as f:
            json.dump(allocation_result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 任务分配完成，结果已保存到 task_allocation_output.json")

        # 运行仿真
        print('\n' + '-' * 70)
        print('【步骤2】启动仿真推演...')
        print('-' * 70)
        print('\n【重要】Tacview使用说明:')
        print('  1. 打开 Tacview 软件')
        print('  2. 点击菜单: File -> Import Data from Real-Time Source')
        print('  3. 输入地址: 127.0.0.1:58008')
        print('  4. 点击 Connect')
        print('  5. 返回本程序等待连接...\n')
        
        simulation = DroneSimulation(allocation_result, control_file_path=control_file)
        
        # 使用默认的仿真步数（减少步数以配合较长的间隔时间）
        simulation.run_simulation(steps=1000)
        
        print('\n' + '=' * 70)
        print('✓✓✓ 仿真推演完成 ✓✓✓')
        print('=' * 70 + '\n')
        
    except KeyboardInterrupt:
        print('\n\n【提示】用户中断程序')
        sys.exit(0)
    except Exception as e:
        print('\n' + '!' * 70)
        print(f'【错误】执行过程中发生错误')
        print(f'  错误信息: {e}')
        import traceback
        traceback.print_exc()
        print('!' * 70 + '\n')
        sys.exit(1)
