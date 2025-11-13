#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从想定XML文件中提取所有无人机/无人艇的位置信息
"""

import xml.etree.ElementTree as ET


def extract_aircraft_positions(xml_file):
    """
    从XML文件中提取所有实体的位置信息
    
    参数:
        xml_file: XML文件路径
    """
    # 解析XML文件
    tree = ET.parse(xml_file)
    root = tree.getroot()
    
    # 存储所有实体信息
    entities = []
    
    # 查找实体部署下的所有实体（红方和蓝方）
    entity_deployment = root.find('实体部署')
    
    if entity_deployment is not None:
        # 遍历红方和蓝方
        for side in entity_deployment:
            side_name = side.tag  # 红方或蓝方
            
            # 遍历各个领域（空中、水面等）
            for domain in side:
                domain_name = domain.tag  # 空中、水面、水下等
                
                # 遍历该领域下的所有实体
                for entity in domain.findall('实体'):
                    entity_id = entity.get('ID')
                    name = entity.find('名称')
                    model = entity.find('型号')
                    position = entity.find('位置')
                    entity_type = entity.find('实体类型')
                    
                    if position is not None and name is not None:
                        # 解析位置信息（格式：经度,纬度,高度）
                        pos_text = position.text
                        lon, lat, alt = pos_text.split(',')
                        
                        entities.append({
                            'side': side_name,
                            'domain': domain_name,
                            'id': entity_id,
                            'name': name.text,
                            'model': model.text if model is not None else 'N/A',
                            'type': entity_type.text if entity_type is not None else 'N/A',
                            'longitude': float(lon),
                            'latitude': float(lat),
                            'altitude': float(alt)
                        })
    
    return entities


def print_positions(entities):
    """
    格式化打印实体位置信息
    
    参数:
        entities: 实体信息列表
    """
    print("=" * 100)
    print(f"{'阵营':<6} {'领域':<8} {'ID':<8} {'名称':<20} {'型号':<20} {'经度':<12} {'纬度':<12} {'高度(m)':<10}")
    print("=" * 100)
    
    for entity in entities:
        print(f"{entity['side']:<6} "
              f"{entity['domain']:<8} "
              f"{entity['id']:<8} "
              f"{entity['name']:<20} "
              f"{entity['model']:<20} "
              f"{entity['longitude']:<12.6f} "
              f"{entity['latitude']:<12.6f} "
              f"{entity['altitude']:<10.2f}")
    
    print("=" * 100)
    print(f"\n总计: {len(entities)} 个实体")
    
    # 统计信息
    red_count = sum(1 for e in entities if e['side'] == '红方')
    blue_count = sum(1 for e in entities if e['side'] == '蓝方')
    print(f"红方: {red_count} 个 | 蓝方: {blue_count} 个")


def export_to_csv(entities, output_file='aircraft_positions.csv'):
    """
    将位置信息导出到CSV文件
    
    参数:
        entities: 实体信息列表
        output_file: 输出文件名
    """
    import csv
    
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        fieldnames = ['阵营', '领域', 'ID', '名称', '型号', '类型', '经度', '纬度', '高度(m)']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        
        writer.writeheader()
        for entity in entities:
            writer.writerow({
                '阵营': entity['side'],
                '领域': entity['domain'],
                'ID': entity['id'],
                '名称': entity['name'],
                '型号': entity['model'],
                '类型': entity['type'],
                '经度': entity['longitude'],
                '纬度': entity['latitude'],
                '高度(m)': entity['altitude']
            })
    
    print(f"\n位置信息已导出到: {output_file}")


if __name__ == '__main__':
    # XML文件路径
    xml_file = '想定示例-无中心模式空战博弈（10机+4机2艇）.xml'
    
    print(f"正在读取文件: {xml_file}\n")
    
    # 提取位置信息
    entities = extract_aircraft_positions(xml_file)
    
    # 打印位置信息
    print_positions(entities)
    
    # 导出到CSV（可选）
    export_to_csv(entities)

