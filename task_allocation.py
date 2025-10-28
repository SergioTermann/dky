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
        
        # 数据格式
        self.tel_file_header = "FileType=text/acmi/tacview\nFileVersion=2.2\n"
        self.tel_reference_time_format = '0,ReferenceTime=%Y-%m-%dT%H:%M:%SZ\n'
        self.tel_data_format = '#{:.2f}\n{},T={:.7f}|{:.7f}|{:.7f}|{:.1f}|{:.1f}|{:.1f},AGL={:.3f},TAS={:.3f},CAS={:.3f},Type=Air+F-16,Name={},Color={},Coalition={}\n'
        
    def start_server(self):
        """启动Tacview服务器"""
        try:
            self.socket = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP)
            self.socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)  # 允许端口重用
            self.socket.bind((self.local_ip, self.local_port))
            self.socket.listen()
            print(f"Tacview服务器启动，监听 {self.local_ip}:{self.local_port}")
            
            # 设置超时，避免无限等待
            self.socket.settimeout(5.0)
            
            try:
                # 等待客户端连接
                self.client_socket, addr = self.socket.accept()
                print(f"Tacview客户端已连接: {addr}")
                
                # 发送握手数据
                self.client_socket.send(self.handshake_data1.encode('utf-8'))
                self.client_socket.send(self.handshake_data2.encode('utf-8'))
                self.client_socket.send(self.handshake_data3.encode('utf-8'))
                self.client_socket.send(b'\x00')
                
                # 接收握手响应
                data = self.client_socket.recv(1024)
                print(f'握手响应: {data}')
                
                # 发送文件头和参考时间
                self.client_socket.send(self.tel_file_header.encode('utf-8'))
                current_time = time.strftime(self.tel_reference_time_format, time.gmtime()).encode('utf-8')
                self.client_socket.send(current_time)
                
                self.is_connected = True
                print('Tacview服务器准备就绪，可以发送数据')
                return True
                
            except timeout:
                print("等待Tacview客户端连接超时，将继续运行仿真（无Tacview显示）")
                self.is_connected = False
                return False
            
        except Exception as e:
            print(f"启动Tacview服务器失败: {e}")
            return False
    
    def send_drone_data(self, drone_id, position, velocity, drone_type, timestamp):
        """发送无人机数据到Tacview"""
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
            agl = altitude - 10  # 地面高度
            tas = speed * 3.6  # 转换为km/h
            cas = tas * 0.9  # 校准空速
            
            # 设置颜色和阵营
            if drone_type == 'attack':
                color = 'Red'
                coalition = 'Enemies'
                name = f'Attack_{drone_id}'
            else:
                color = 'Blue'
                coalition = 'Allies'
                name = f'Defense_{drone_id}'
            
            # 生成唯一ID (基于drone_id)
            object_id = 3000000 + hash(drone_id) % 100000
            
            # 格式化数据
            data = self.tel_data_format.format(
                timestamp, object_id, longitude, latitude, altitude, 
                roll, pitch, yaw, agl, tas, cas, name, color, coalition
            )
            
            # 发送数据
            self.client_socket.send(data.encode('utf-8'))
            return True
            
        except Exception as e:
            print(f"发送Tacview数据失败: {e}")
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
        """计算单个无人机的Shapley值"""
        shapley_value = 0.0
        other_drones = [d for d in self.U if d != drone]
        n = len(self.U)

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
        for drone in self.U:
            self.shapley_values[drone] = self.calculate_shapley_value(drone)

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

    def execute_task_allocation(self) -> Dict:
        """执行完整的任务分配流程"""
        # 计算Shapley值
        self.compute_all_shapley_values()

        # 初始化分组
        groups = self.initialize_task_groups()

        # 分配攻击无人机
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
    
    # 将经纬度转换为弧度
    lat = math.radians(aircraft['latitude'])
    lon = math.radians(aircraft['longitude'])
    
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

def load_situation_data(json_file):
    """从JSON文件加载态势数据"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
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
    
    # 创建任务分配系统
    allocator = GameBasedTaskAllocation(attack_drones_data, defense_drones_data)
    
    # 执行任务分配
    allocation_result = allocator.execute_task_allocation()
    
    # 添加初始位置信息到结果中
    allocation_result['initial_positions'] = initial_positions
    
    return allocation_result


# 4. Simulation class
class DroneSimulation:
    """Simulates drone movements and streams to Tacview"""

    def __init__(self, allocation_result, target_area=(80, 80), area_size=100, 
                 enable_status_broadcast=True, status_broadcast_port=10114):
        self.allocation_result = allocation_result
        self.target_area = target_area
        self.area_size = area_size
        
        # 仿真控制参数
        self.control_file_path = "simulation_control.json"
        self.is_paused = False
        self.speed_multiplier = 1.0
        self.last_control_check = time.time()
        
        # 飞行动力学参数
        self.max_speed = 15.0  # 最大速度 (m/s)
        self.max_acceleration = 5.0  # 最大加速度 (m/s²)
        self.max_angular_velocity = 45.0  # 最大角速度 (度/秒)
        self.smoothing_factor = 0.1  # 平滑系数
        
<<<<<<< HEAD
        # 态势广播设置
        self.enable_status_broadcast = enable_status_broadcast
        self.status_broadcast_port = status_broadcast_port
        self.status_socket = None
        
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
    
    def _init_status_broadcast(self):
        """初始化态势广播UDP套接字"""
        try:
            self.status_socket = socket(AF_INET, SOCK_DGRAM)
            print(f"态势广播已初始化，目标端口: 127.0.0.1:{self.status_broadcast_port}")
        except Exception as e:
            print(f"初始化态势广播套接字失败: {e}")
            self.enable_status_broadcast = False
    
    def _broadcast_status(self):
        """广播当前红方态势数据到本地UDP端口"""
        if not self.enable_status_broadcast or not self.status_socket:
            return
        
        try:
            # 构造红方态势数据
            red_aircraft_list = []
            
            for drone_id in self.drone_positions:
                # 获取无人机的类型（攻击或防御）
                drone_type = self.allocation_result['initial_positions'][drone_id]['type']
                
                # 只发送攻击型无人机（红方）
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
            
            # 发送数据到本地UDP端口
            if red_aircraft_list:
                data = json.dumps({
                    'timestamp': time.time(),
                    'red_aircraft': red_aircraft_list
                }, ensure_ascii=False)
                
                self.status_socket.sendto(
                    data.encode('utf-8'),
                    ('127.0.0.1', self.status_broadcast_port)
                )
                
        except Exception as e:
            # 静默失败，不影响主仿真
            pass
=======
        # 无人机状态
        self.drone_positions = {}
        self.drone_velocities = {}
        self.drone_accelerations = {}
        self.drone_headings = {}
        self.drone_angular_velocities = {}
        
        # Tacview连接
        self.tacview_streamer = None
        self._start_tacview_server()

    def _start_tacview_server(self):
        """Start Tacview server for real-time visualization"""
        try:
            self.tacview_streamer = TacviewStreamer()
            self.tacview_streamer.start_server()
            print("Tacview服务器已启动，等待连接...")
        except Exception as e:
            print(f"启动Tacview服务器失败: {e}")
            self.tacview_streamer = None

    def check_control_file(self):
        """检查控制文件并更新仿真状态"""
        try:
            if os.path.exists(self.control_file_path):
                with open(self.control_file_path, 'r', encoding='utf-8') as f:
                    control_data = json.load(f)
                    
                self.is_paused = control_data.get('paused', False)
                self.speed_multiplier = control_data.get('speed_multiplier', 1.0)
                
                # 限制速度倍数在合理范围内
                self.speed_multiplier = max(0.1, min(10.0, self.speed_multiplier))
                
        except Exception as e:
            # 如果读取控制文件失败，使用默认值
            self.is_paused = False
            self.speed_multiplier = 1.0

    def create_default_control_file(self):
        """创建默认的控制文件"""
        try:
            control_data = {
                'paused': False,
                'speed_multiplier': 1.0
            }
            with open(self.control_file_path, 'w', encoding='utf-8') as f:
                json.dump(control_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"创建控制文件失败: {e}")
>>>>>>> 1b996388358ad1967b7526d3e2ae3cda8e343fed

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
        dt = 0.1  # 基础时间步长 (秒)
        
        step = 0
        while step < steps:
            # 每秒检查一次控制文件
            current_time = time.time()
            if current_time - self.last_control_check > 1.0:
                self.check_control_file()
                self.last_control_check = current_time
            
            # 如果暂停，跳过位置更新但继续检查控制文件
            if self.is_paused:
                # 每50次循环输出一次暂停状态
                if int(current_time * 10) % 50 == 0:  # 大约每5秒输出一次
                    print(f"仿真进度: {step}/{steps} 步 ({step/steps*100:.1f}%) - 状态: 暂停")
                time.sleep(0.1)
                continue
            
            # 只有在非暂停状态下才递增步数
            step += 1
            
            # 根据速度倍数调整时间步长
            actual_dt = dt * self.speed_multiplier
            
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
                    angular_velocity += angular_accel * actual_dt
                    angular_velocity = np.clip(angular_velocity, -self.max_angular_velocity, self.max_angular_velocity)
                    current_heading += angular_velocity * actual_dt
                    
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
                    vx = vx * self.smoothing_factor + (vx + accel_x * actual_dt) * (1 - self.smoothing_factor)
                    vy = vy * self.smoothing_factor + (vy + accel_y * actual_dt) * (1 - self.smoothing_factor)
                    
                    # 限制速度
                    speed = math.sqrt(vx**2 + vy**2)
                    if speed > self.max_speed:
                        vx = vx / speed * self.max_speed
                        vy = vy / speed * self.max_speed
                    
                    # 更新位置
                    new_x = x + vx * actual_dt
                    new_y = y + vy * actual_dt
                    
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
                    
                    # 发送Tacview数据
                    if self.tacview_streamer and self.tacview_streamer.is_connected:
                        try:
                            # 转换为Tacview坐标系 (经纬度和高度)
                            position = (new_x, new_y, 1000 + np.random.uniform(-50, 50))  # 添加高度变化
                            velocity = (vx * 10, vy * 10, 0)  # 适当放大速度以便在Tacview中可见
                            timestamp = time.time()
                            
                            self.tacview_streamer.send_drone_data(
                                drone_id, position, velocity, drone_type, timestamp
                            )
                        except Exception as e:
                            # 忽略Tacview发送错误，继续仿真
                            pass

            # 每50步输出一次进度
            if step % 50 == 0:
                status = "暂停" if self.is_paused else f"运行 (速度: {self.speed_multiplier}x)"
                print(f"仿真进度: {step}/{steps} 步 ({step/steps*100:.1f}%) - 状态: {status}")
            
<<<<<<< HEAD
            # 广播红方态势数据（每10步广播一次，减少数据量）
            # if step % 10 == 0:
            self._broadcast_status()

            # 每步之间增加间隔时间，让仿真更真实
            time.sleep(0.1)  # 每步间隔0.1秒，让Tacview能更好地显示动画
=======
            # 根据速度倍数调整睡眠时间
            sleep_time = 0.1 / max(0.1, self.speed_multiplier)
            time.sleep(sleep_time)
>>>>>>> 1b996388358ad1967b7526d3e2ae3cda8e343fed

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
        """Run the full simulation"""
        # 创建默认控制文件
        self.create_default_control_file()
        
        self.initialize_positions()
        print("开始无人机仿真...")
        print(f"控制文件路径: {self.control_file_path}")
        print("可以通过界面按钮控制仿真的暂停/继续和速度")
        
        self.update_positions(steps)
        metrics = self.calculate_performance_metrics()

        print("\n=== 仿真性能指标 ===")
        print(f"平均距离目标: {metrics['avg_distance_to_target']:.2f}")
        print("编队内聚性:")
        for group_id, cohesion in metrics['group_cohesion'].items():
            print(f"  编队 {group_id}: {cohesion:.2f}")

        print("\n仿真完成！")
        
        # 关闭Tacview连接
        if self.tacview_streamer:
            try:
                self.tacview_streamer.close()
            except Exception as e:
                # 忽略关闭时的错误
                pass
        
        return metrics


# 5. Main execution
def select_json_file():
    """使用文件对话框选择JSON文件"""
    # 创建一个隐藏的根窗口
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    
    # 打开文件选择对话框
    file_path = filedialog.askopenfilename(
        title="选择态势JSON文件",
        filetypes=[
            ("JSON文件", "*.json"),
            ("所有文件", "*.*")
        ],
        initialdir=os.getcwd()  # 默认打开当前目录
    )
    
    # 销毁根窗口
    root.destroy()
    
    return file_path


if __name__ == "__main__":
    # 检查命令行参数
    if len(sys.argv) > 1:
        situation_file = sys.argv[1]
        print(f"使用指定的态势文件: {situation_file}")
    else:
        # 弹出文件选择对话框
        print("请选择态势JSON文件...")
        situation_file = select_json_file()
        
        if not situation_file:
            print("未选择文件，程序退出。")
            sys.exit(0)
        
        print(f"选择的态势文件: {situation_file}")
    
    # 检查文件是否存在
    import os
    if not os.path.exists(situation_file):
        print(f"错误：找不到态势文件 {situation_file}")
        sys.exit(1)
    
    try:
        # 执行任务分配
        allocation_result = execute_task_allocation(situation_file)
        
        # 保存结果到JSON文件
        with open('task_allocation_output.json', 'w', encoding='utf-8') as f:
            json.dump(allocation_result, f, indent=2, ensure_ascii=False)
        
        print(f"任务分配结果已保存到 task_allocation_output.json")

        # 运行仿真
        print("开始无人机任务分配仿真...")
        print("启用Tacview模式 - 请在Tacview中连接到 127.0.0.1:58008")
        
        simulation = DroneSimulation(allocation_result)
        
        # 使用默认的仿真步数（减少步数以配合较长的间隔时间）
        simulation.run_simulation(steps=1000)
        
    except Exception as e:
        print(f"执行过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
