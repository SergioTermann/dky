import math
import time

CONSTANTS_RADIUS_OF_EARTH = 6378137.     # meters (m)
LOCALIP = "127.0.0.1"
LOCALPORT = 5005
import random
import csv
from socket import *


sphere_centers = [
    [-10000, -40000, 6000],  # 第一个球体圆心
    [10000, -50000, 6000],  # 第二个球体圆心
    [20000, -60000, 6000],  # 第三个球体圆心
    [30000, -70000, 6000]  # 第四个球体圆心
]

lat = -7.008889
lon = 106.988333


def XYtoGPS(x, y, ref_lat=lat, ref_lon=lon):
    x_rad = float(x) / CONSTANTS_RADIUS_OF_EARTH
    y_rad = float(y) / CONSTANTS_RADIUS_OF_EARTH
    c = math.sqrt(x_rad * x_rad + y_rad * y_rad)

    ref_lat_rad = math.radians(ref_lat)
    ref_lon_rad = math.radians(ref_lon)

    ref_sin_lat = math.sin(ref_lat_rad)
    ref_cos_lat = math.cos(ref_lat_rad)

    if abs(c) > 0:
        sin_c = math.sin(c)
        cos_c = math.cos(c)

        lat_rad = math.asin(cos_c * ref_sin_lat + (x_rad * sin_c * ref_cos_lat) / c)
        lon_rad = (ref_lon_rad + math.atan2(y_rad * sin_c, c * ref_cos_lat * cos_c - x_rad * ref_sin_lat * sin_c))

        lat = math.degrees(lat_rad)
        lon = math.degrees(lon_rad)

    else:
        lat = math.degrees(ref_lat)
        lon = math.degrees(ref_lon)

    return lat, lon


class fourty_ally():
    def __init__(self, host='192.168.5.4', port='57805', rendering=True) -> None:
        self.x_target = []
        self.y_target = []
        self.z_target = []
        self.x_current_ally = []
        self.y_current_ally = []
        self.z_current_ally = []
        self.x_current_enemy = []
        self.y_current_enemy = []
        self.z_current_enemy = []
        self.total_x_loc_ally = []
        self.total_y_loc_ally = []
        self.total_x_loc_enemy = []
        self.total_y_loc_enemy = []
        self.total_z_loc_ally = []
        self.total_z_loc_enemy = []
        self.step_game = 0
        self.message = ''
        self.target_loc1 = []
        self.target_loc2 = []
        self.target_loc3 = []
        self.target_loc4 = []
        self.target = []
        self.target_ally = []
        self.team_target_index = [0, 0, 0, 0]
        self.team_speed_percentage = [1, 1, 1, 1]
        self.start_cool = False
        self.save_blue = False
        self.total_time = 0

    def reset(self, coordination_time):
        self.total_time = coordination_time
        self.x_current_ally, self.y_current_ally, self.z_current_ally = self.generate_initial_positions_ally(sphere_centers)
        self.x_current_enemy, self.y_current_enemy, self.z_current_enemy = self.generate_initial_positions_enemmy(0, 200000, 6000)
        self.x_early_enemy, self.y_early_enemy, self.z_early_enemy = self.generate_initial_positions_enemmy(0, 160000, 6000, 10)
        self.x_target, self.y_target, self.z_target = self.generate_initial_positions_ally([[0, 0, 6000], [0, 0, 6000], [0, 0, 6000], [0, 0, 6000]], 4)
        self.target = [
            [[0, 0, 6000], [0, 0, 6000], [0, 0, 6000], [0, 0, 6000]],
            [[3000, 20000, 6000], [3000, 20000, 6000], [3000, 20000, 6000], [3000, 20000, 6000]],
            [[0, 30000, 6000], [0, 30000, 6000], [0, 30000, 6000], [0, 30000, 6000]],
            [[-2500, 40000, 6000], [-2500, 40000, 6000], [-2500, 40000, 6000], [-2500, 40000, 6000]],
            [[2500, 50000, 6000], [2500, 50000, 6000], [2500, 50000, 6000], [2500, 50000, 6000]],
            [[-7500, 150000, 6000], [15000, 150000, 6000], [7500, 150000, 6000], [0, 150000, 6000]],
        ]
        for loc in self.target:
            self.target_ally.append(self.generate_initial_positions_ally(loc))


    def step(self, delay_time, start_coor=True, slow_down=False):
        self.start_cool = start_coor
        time.sleep((delay_time))
        self.step_game += 1
        self.message = ''
        if self.step_game == self.total_time:
            for ally_fighter in range(40):
                self.total_x_loc_ally.append(self.x_current_ally[ally_fighter])
                self.total_y_loc_ally.append(self.y_current_ally[ally_fighter] + self.step_game * 20)
                self.total_z_loc_ally.append(self.z_current_ally[ally_fighter])
            for enemy_fighter in range(40):
                self.total_x_loc_enemy.append(self.x_current_enemy[enemy_fighter])
                self.total_y_loc_enemy.append(self.y_current_enemy[enemy_fighter] - self.step_game * 20)
                self.total_z_loc_enemy.append(self.z_current_enemy[enemy_fighter])
            self.save_coordinates_to_csv(self.total_x_loc_ally, self.total_y_loc_ally, self.total_z_loc_ally,
                                         filename="ally_coordinates.csv")
            self.save_coordinates_to_csv(self.total_x_loc_enemy, self.total_y_loc_enemy, self.total_z_loc_enemy,
                                         filename="enemy_coordinates.csv")
        if not self.start_cool:
            for enemy_fighter in range(10):
                lat, lon = XYtoGPS(self.x_early_enemy[enemy_fighter], self.y_early_enemy[enemy_fighter] - 60 * self.step_game)
                self.message += "{},T={}|{}|{}|{}|{}|{},Type=Air+FixedWing,Coalition=Enemies,Color=Blue,Name=F-16,Mach=0.800, ShortName=F-16  0  3.00,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10, RadarVerticalBeamwidth=10".format(
                    enemy_fighter + 2000, lon, lat, self.z_current_enemy[enemy_fighter], 0, 0, 270) + "\n"
        else:
            if not self.save_blue:
                for enemy_fighter in range(10):
                    self.y_early_enemy[enemy_fighter] = self.y_early_enemy[enemy_fighter] - 60 * self.step_game
                self.save_coordinates_to_csv(self.x_early_enemy, self.y_early_enemy, self.z_early_enemy, 'enemy_early.csv')
                self.save_blue = True

        if slow_down:
            for ally_fighter in range(40):
                lat, lon = XYtoGPS(self.x_current_ally[ally_fighter],
                                   self.y_current_ally[ally_fighter] + 5 * self.step_game)
                self.message += "{},T={}|{}|{}|{}|{}|{},Type=Air+FixedWing,Coalition=Enemies,Color=Red,Name=F-16,Mach=0.800, ShortName=F-16  0  3.00,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10, RadarVerticalBeamwidth=10".format(
                    ally_fighter + 1010, lon, lat, self.z_current_enemy[ally_fighter], 0, 0, 90) + "\n"

            for enemy_fighter in range(40):
                lat, lon = XYtoGPS(self.x_current_enemy[enemy_fighter],
                                   self.y_current_enemy[enemy_fighter] - 5 * self.step_game)
                self.message += "{},T={}|{}|{}|{}|{}|{},Type=Air+FixedWing,Coalition=Enemies,Color=Blue,Name=F-16,Mach=0.800, ShortName=F-16  0  3.00,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10, RadarVerticalBeamwidth=10".format(
                    enemy_fighter + 2010, lon, lat, self.z_current_enemy[enemy_fighter], 0, 0, 270) + "\n"
        else:
            for ally_fighter in range(40):
                x, y, yaw = self.update_position_and_yaw(ally_fighter)
                self.x_current_ally[ally_fighter] = x
                self.y_current_ally[ally_fighter] = y
                lat, lon = XYtoGPS(x, y)
                self.message += "#{}\n".format(self.step_game/10)+"{},T={}|{}|{}|{}|{}|{},Type=Air+FixedWing,Coalition=Enemies,Color=Red,Name=F-16,Mach=0.800, ShortName=F-16  0  3.00,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10, RadarVerticalBeamwidth=10".format(
                    ally_fighter + 1010, lon, lat, self.z_current_ally[ally_fighter], 0, 0, yaw) + "\n"

            for enemy_fighter in range(40):
                lat, lon = XYtoGPS(self.x_current_enemy[enemy_fighter], self.y_current_enemy[enemy_fighter] - 20 * self.step_game)
                self.message += "{},T={}|{}|{}|{}|{}|{},Type=Air+FixedWing,Coalition=Enemies,Color=Blue,Name=F-16,Mach=0.800, ShortName=F-16  0  3.00,RadarMode=1,RadarRange=2000,RadarHorizontalBeamwidth=10, RadarVerticalBeamwidth=10".format(
                    enemy_fighter + 2010, lon, lat, self.z_current_enemy[enemy_fighter], 0, 0, 270) + "\n"
        with socket(AF_INET, SOCK_DGRAM) as so:
            so.sendto(''.join([self.message]).encode('utf-8'), (LOCALIP, LOCALPORT))
        if self.step_game > self.total_time:
            return True
        return False

    def generate_initial_positions_ally(self, sphere_centers, num_rows=4, spacing=1500):
        x_positions = []
        y_positions = []
        z_positions = []

        for center in sphere_centers:
            center_x, center_y, center_z = center
            # 生成倒置三角形队形
            for row in range(num_rows):  # 从第0行到第num_rows-1行
                num_aircraft = num_rows - row  # 每行的飞机数量逐渐减少
                for col in range(num_aircraft):  # 遍历当前行的飞机数量
                    # 计算飞机的偏移位置
                    x_offset = (col - (num_aircraft - 1) / 2) * spacing  # 水平偏移，居中排列
                    y_offset = row * spacing  # 每行向前（或向后）偏移
                    z_offset = 0  # 保持在同一高度

                    # 添加飞机位置
                    x_positions.append(center_x + x_offset)
                    y_positions.append(center_y + y_offset)
                    z_positions.append(center_z + z_offset)

        return x_positions, y_positions, z_positions

    def generate_initial_positions_enemmy(self, center_x, center_y, center_z, num_aircraft=40, sphere_radius=4000):
        x_positions = []
        y_positions = []
        z_positions = []

        for _ in range(num_aircraft):
            # 生成球坐标参数
            r = sphere_radius * pow(random.random(), 1 / 3)
            theta = math.acos(2 * random.random() - 1)  # 天顶角
            phi = random.uniform(0, 2 * math.pi)  # 方位角

            # 转换为笛卡尔坐标并加上中心点偏移
            x_positions.append(center_x + r * math.sin(theta) * math.cos(phi))
            y_positions.append(center_y + r * math.sin(theta) * math.sin(phi))
            z_positions.append(center_z + r * math.cos(theta))

        return x_positions, y_positions, z_positions

    def save_coordinates_to_csv(self, x_positions, y_positions, z_positions, filename="coordinates.csv"):
        filename = 'C:\\Users\\bafs\\Desktop\\human-machine_intelligence\\' + filename
        if len(x_positions) != len(y_positions):
            raise ValueError("x_positions 和 y_positions 的长度不一致！")

            # 打开文件并写入数据
        with open(filename, mode="a", newline="") as file:
            writer = csv.writer(file)
            # 写入每一对坐标
            for x, y, z in zip(x_positions, y_positions, z_positions):
                writer.writerow([x, y, z])

        print(f"坐标已保存到 {filename}")

    def update_position_and_yaw(self, ally_fighter,  init_speed=56):
        target_x = self.target_ally[self.team_target_index[int(ally_fighter / 10)]][0][ally_fighter]
        target_y = self.target_ally[self.team_target_index[int(ally_fighter / 10)]][1][ally_fighter]
        x = self.x_current_ally[ally_fighter]
        y = self.y_current_ally[ally_fighter]
        # 计算飞机到 (0, 0) 的方向向量
        dx = target_x - x
        dy = target_y - y

        # 计算到 (0, 0) 的距离
        distance = math.sqrt(dx ** 2 + dy ** 2)
        if (ally_fighter + 1) % 10 == 0:
            if distance < 100:
                self.team_target_index[int(ally_fighter / 10)] += 1
                if self.team_target_index[int(ally_fighter / 10)] >= (len(self.target) -1):
                    self.team_speed_percentage[int(ally_fighter / 10)] *= 0.6

            # 计算单位方向向量
        unit_dx = dx / distance
        unit_dy = dy / distance

        speed = init_speed * self.team_speed_percentage[int(ally_fighter / 10)]
        # 根据速度计算新的位置
        new_x = x + unit_dx * speed
        new_y = y + unit_dy * speed

        # 计算偏航角（yaw），以 (0, 0) 为目标
        yaw = math.degrees(math.atan2(dy, dx))  # atan2 返回弧度，转换为度

        return new_x, new_y, yaw

