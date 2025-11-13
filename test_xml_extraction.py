#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试XML想定文件的红方位置提取功能
"""

import xml.etree.ElementTree as ET


def extract_red_aircraft_from_scenario(xml_file):
    """
    从想定XML文件中提取红方无人机位置信息
    
    参数:
        xml_file: XML想定文件路径
    
    返回:
        红方无人机列表
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    red_aircraft = []
    
    # 查找实体部署 -> 红方 -> 空中 -> 实体
    entity_deployment = root.find('实体部署')
    if entity_deployment is not None:
        red_side = entity_deployment.find('红方')
        if red_side is not None:
            air_domain = red_side.find('空中')
            if air_domain is not None:
                # 遍历所有空中实体
                for entity in air_domain.findall('实体'):
                    entity_id = entity.get('ID')
                    name_elem = entity.find('名称')
                    model_elem = entity.find('型号')
                    position_elem = entity.find('位置')
                    
                    if position_elem is not None and position_elem.text:
                        # 解析位置（格式：经度,纬度,高度）
                        pos_parts = position_elem.text.split(',')
                        if len(pos_parts) >= 3:
                            longitude = float(pos_parts[0])
                            latitude = float(pos_parts[1])
                            altitude = float(pos_parts[2])
                            
                            aircraft_data = {
                                'id': entity_id,
                                'name': name_elem.text if name_elem is not None else 'Unknown',
                                'model': model_elem.text if model_elem is not None else 'Unknown',
                                'longitude': longitude,
                                'latitude': latitude,
                                'altitude': altitude
                            }
                            
                            red_aircraft.append(aircraft_data)
    
    return red_aircraft


if __name__ == '__main__':
    # 测试提取功能
    xml_file = '想定示例-无中心模式空战博弈（10机+4机2艇）.xml'
    
    print(f"正在从文件中提取红方无人机位置: {xml_file}\n")
    
    red_aircraft = extract_red_aircraft_from_scenario(xml_file)
    
    print("=" * 100)
    print(f"{'编号':<10} {'名称':<20} {'型号':<20} {'经度':<15} {'纬度':<15} {'高度(m)':<10}")
    print("=" * 100)
    
    for aircraft in red_aircraft:
        print(f"{aircraft['id']:<10} "
              f"{aircraft['name']:<20} "
              f"{aircraft['model']:<20} "
              f"{aircraft['longitude']:<15.6f} "
              f"{aircraft['latitude']:<15.6f} "
              f"{aircraft['altitude']:<10.2f}")
    
    print("=" * 100)
    print(f"\n总计提取: {len(red_aircraft)} 架红方无人机")
    print("\n✓ 提取功能测试成功！")

