#ifndef AIRCRAFT_H
#define AIRCRAFT_H

#include <QString>
#include <QJsonObject>

struct Aircraft {
    int id;
    QString type;
    double longitude;
    double latitude;
    double altitude;
    double speed;
    double heading;
    QString status;

    Aircraft() : id(0), longitude(0), latitude(0), altitude(0), speed(0), heading(0) {}

    // 8参数构造函数
    Aircraft(int _id, const QString& _type, double _lon, double _lat,
             double _alt, double _spd, double _hdg, const QString& _status)
        : id(_id), type(_type), longitude(_lon), latitude(_lat),
        altitude(_alt), speed(_spd), heading(_hdg), status(_status) {}

    QJsonObject toJson() const {
        QJsonObject obj;
        obj["id"] = id;
        obj["type"] = type;
        obj["longitude"] = longitude;
        obj["latitude"] = latitude;
        obj["altitude"] = altitude;
        obj["speed"] = speed;
        obj["heading"] = heading;
        obj["status"] = status;
        return obj;
    }

    static Aircraft fromJson(const QJsonObject& obj) {
        Aircraft aircraft;
        aircraft.id = obj["id"].toInt();
        aircraft.type = obj["type"].toString();
        aircraft.longitude = obj["longitude"].toDouble();
        aircraft.latitude = obj["latitude"].toDouble();
        aircraft.altitude = obj["altitude"].toDouble();
        aircraft.speed = obj["speed"].toDouble();
        aircraft.heading = obj["heading"].toDouble();
        aircraft.status = obj["status"].toString();
        return aircraft;
    }
};

#endif // AIRCRAFT_H
