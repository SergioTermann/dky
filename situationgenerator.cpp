#include "situationgenerator.h"

SituationGenerator::GenerationResult SituationGenerator::generateBlueSituation(
    const QList<Aircraft>& redAircraftList,
    int userBlueCount,
    const QString& userStrategy)
{
    GenerationResult result;

    // 输入验证
    if (redAircraftList.isEmpty()) {
        result.success = false;
        result.errorMessage = "红方数据为空，无法生成蓝方态势";
        return result;
    }

    // 1. 分析红方态势
    int redCount = redAircraftList.size();

    // 2. 计算推荐参数
    result.recommendedBlueCount = redCount + 2; // 建议蓝方数量比红方多2架
    result.recommendedStrategy = "中等"; // 默认使用中等难度

    // 3. 确定最终参数
    int finalBlueCount = (userBlueCount > 0) ? userBlueCount : result.recommendedBlueCount;
    QString finalStrategy = (!userStrategy.isEmpty()) ? userStrategy : result.recommendedStrategy;

    // 4. 生成蓝方飞机列表
    for (int i = 0; i < finalBlueCount; i++) {
        Aircraft blueAircraft;
        blueAircraft.id = i + 1;
        blueAircraft.type = QString("蓝方飞机%1").arg(i + 1);
        blueAircraft.longitude = qrand() % 1000; // 随机经度
        blueAircraft.latitude = qrand() % 1000; // 随机纬度
        blueAircraft.altitude = 5000 + qrand() % 5000; // 随机高度5000-10000
        blueAircraft.speed = 400 + qrand() % 200; // 随机速度400-600
        blueAircraft.heading = qrand() % 360; // 随机航向0-359
        blueAircraft.status = "待命"; // 初始状态
        result.blueAircraftList.append(blueAircraft);
    }

    // 5. 返回结果
    result.success = true;
    return result;
}
