import numpy as np
from itertools import combinations
from typing import List, Dict, Set, Tuple, Union
from dataclasses import dataclass
import math
import json
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import time
import sys


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
    for i, aircraft in enumerate(data.get('red_aircraft', [])):
        # 转换为xyz坐标
        coords = convert_to_xyz(aircraft)
        # 计算到目标的距离
        distance = math.sqrt(coords['x']**2 + coords['y']**2 + coords['z']**2)
        # 将速度转换为机动性和动力
        speed = math.sqrt(coords['vx']**2 + coords['vy']**2 + coords['vz']**2)
        mobility = min(1.0, speed / 1000)  # 假设最大速度为1000
        power = min(1.0, coords['z'] / 10000)  # 假设最大高度为10000
        
        attack_drones_data[f'A{i+1}'] = {
            'mobility': mobility,
            'power': power,
            'distance_to_target': distance
        }
    
    # 将蓝方飞机转换为防御无人机数据
    defense_drones_data = {}
    for i, aircraft in enumerate(data.get('blue_aircraft', [])):
        # 转换为xyz坐标
        coords = convert_to_xyz(aircraft)
        # 计算到目标的距离
        distance = math.sqrt(coords['x']**2 + coords['y']**2 + coords['z']**2)
        # 将速度转换为机动性和动力
        speed = math.sqrt(coords['vx']**2 + coords['vy']**2 + coords['vz']**2)
        mobility = min(1.0, speed / 1000)  # 假设最大速度为1000
        power = min(1.0, coords['z'] / 10000)  # 假设最大高度为10000
        
        defense_drones_data[f'D{i+1}'] = {
            'mobility': mobility,
            'power': power,
            'distance_to_target': distance
        }
    
    return attack_drones_data, defense_drones_data

def execute_task_allocation(json_file):
    """执行任务分配"""
    # 从JSON文件加载数据
    attack_drones_data, defense_drones_data = load_situation_data(json_file)
    
    # 创建任务分配系统
    allocator = GameBasedTaskAllocation(attack_drones_data, defense_drones_data)
    
    # 执行任务分配
    allocation_result = allocator.execute_task_allocation()
    
    return allocation_result


# 4. Simulation class
class DroneSimulation:
    """Simulates drone movements and visualizes task allocation results"""

    def __init__(self, allocation_result, target_area=(80, 80), area_size=100):
        self.allocation_result = allocation_result
        self.target_area = target_area
        self.area_size = area_size
        self.drone_positions = {}
        self.fig, self.ax = None, None
        self.drone_markers = {}
        self.group_colors = plt.cm.tab10.colors

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

    def setup_visualization(self):
        """Setup the visualization environment"""
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        self.ax.set_xlim(0, self.area_size)
        self.ax.set_ylim(0, self.area_size)

        # Draw target area
        target = Rectangle((self.target_area[0] - 5, self.target_area[1] - 5), 10, 10,
                           color='red', alpha=0.3, label='Target Area')
        self.ax.add_patch(target)

        # Setup legend for drone types
        self.ax.plot([], [], 'o', color='blue', markersize=8, label='Defense Drone')
        self.ax.plot([], [], 'o', color='red', markersize=8, label='Attack Drone')

        self.ax.set_title('Drone Task Allocation Simulation')
        self.ax.set_xlabel('X Position (km)')
        self.ax.set_ylabel('Y Position (km)')
        self.ax.grid(True)

    def draw_drones(self):
        """Draw all drones with their group assignments"""
        # Clear previous markers
        for marker in self.drone_markers.values():
            if marker in self.ax.collections:
                marker.remove()
        self.drone_markers = {}

        # Draw drones by group
        for i, group in enumerate(self.allocation_result['task_groups']):
            group_color = self.group_colors[i % len(self.group_colors)]

            # Draw defense drones
            for drone_id in group['defense_drones']:
                x, y = self.drone_positions[drone_id]
                marker = self.ax.scatter(x, y, s=150, color='blue', edgecolor=group_color,
                                         linewidth=2, marker='o', label=drone_id)
                self.ax.annotate(drone_id, (x, y), fontsize=8)
                self.drone_markers[drone_id] = marker

            # Draw attack drones
            for drone_id in group['attack_drones']:
                x, y = self.drone_positions[drone_id]
                marker = self.ax.scatter(x, y, s=150, color='red', edgecolor=group_color,
                                         linewidth=2, marker='o', label=drone_id)
                self.ax.annotate(drone_id, (x, y), fontsize=8)
                self.drone_markers[drone_id] = marker

        # Draw connections between drones in same group
        for group in self.allocation_result['task_groups']:
            all_drones = group['defense_drones'] + group['attack_drones']
            for i, drone1 in enumerate(all_drones):
                for drone2 in all_drones[i + 1:]:
                    x1, y1 = self.drone_positions[drone1]
                    x2, y2 = self.drone_positions[drone2]
                    self.ax.plot([x1, x2], [y1, y2], 'k--', alpha=0.2)

        plt.legend(loc='upper right')
        self.fig.canvas.draw()

    def update_positions(self, steps=100):
        """Simulate movement of drones toward target area based on group coordination"""
        for step in range(steps):
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

            # Update positions
            for group in self.allocation_result['task_groups']:
                group_id = group['group_id']
                all_drones = group['defense_drones'] + group['attack_drones']

                # Skip empty groups
                if not all_drones:
                    continue

                # Move toward group center and target
                for drone_id in all_drones:
                    drone_type = 'attack' if drone_id in group['attack_drones'] else 'defense'
                    x, y = self.drone_positions[drone_id]

                    # Weights for movement components
                    target_weight = 0.03
                    group_weight = 0.02

                    # Move toward target
                    dx_target = (self.target_area[0] - x) * target_weight
                    dy_target = (self.target_area[1] - y) * target_weight

                    # Move toward group center
                    if group_id in group_centers:
                        gx, gy = group_centers[group_id]
                        dx_group = (gx - x) * group_weight
                        dy_group = (gy - y) * group_weight
                    else:
                        dx_group, dy_group = 0, 0

                    # Attack drones move faster toward target
                    if drone_type == 'attack':
                        dx_target *= 1.5
                        dy_target *= 1.5

                    # Update position
                    new_x = x + dx_target + dx_group + np.random.normal(0, 0.2)
                    new_y = y + dy_target + dy_group + np.random.normal(0, 0.2)

                    # Ensure within boundaries
                    new_x = np.clip(new_x, 0, self.area_size)
                    new_y = np.clip(new_y, 0, self.area_size)

                    self.drone_positions[drone_id] = (new_x, new_y)

            # Update visualization every 5 steps
            if step % 5 == 0:
                self.draw_drones()
                plt.pause(0.1)

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
        self.initialize_positions()
        self.setup_visualization()
        self.draw_drones()
        plt.pause(1)  # Initial pause to show starting positions

        self.update_positions(steps)
        metrics = self.calculate_performance_metrics()

        print("\nSimulation Performance Metrics:")
        print(f"Average distance to target: {metrics['avg_distance_to_target']:.2f} km")
        print("\nGroup cohesion (avg distance between members):")
        for group_id, cohesion in metrics['group_cohesion'].items():
            print(f"Group {group_id}: {cohesion:.2f} km")

        plt.show()


# 5. Main execution
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("[错误] 请提供态势文件路径作为参数")
        print("用法: python task_allocation.py <态势文件路径>")
        sys.exit(1)
        
    situation_file = sys.argv[1]
    allocation_result = execute_task_allocation(situation_file)
    
    # Save results to JSON
    with open('task_allocation_output.json', 'w', encoding='utf-8') as f:
        json.dump(allocation_result, f, indent=2, ensure_ascii=False)

    # Run the simulation with the results
    print("Starting drone simulation...")
    simulation = DroneSimulation(allocation_result)
    simulation.run_simulation(steps=50)