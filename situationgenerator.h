#ifndef SITUATIONGENERATOR_H
#define SITUATIONGENERATOR_H

#include "aircraft.h"
#include <QList>
#include <QString>

class SituationGenerator
{
public:
    struct GenerationResult {
        QList<Aircraft> blueAircraftList;
        int recommendedBlueCount;
        QString recommendedStrategy;
        bool success;
        QString errorMessage;
    };

    // 静态方法
    static GenerationResult generateBlueSituation(
        const QList<Aircraft>& redAircraftList,
        int userBlueCount = -1,        // -1表示自动计算
        const QString& userStrategy = "" // 空字符串表示自动选择
        );
};

#endif // SITUATIONGENERATOR_H
