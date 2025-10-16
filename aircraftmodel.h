#ifndef AIRCRAFTMODEL_H
#define AIRCRAFTMODEL_H

#include <QAbstractTableModel>
#include <QList>
#include "aircraft.h"

class AircraftModel : public QAbstractTableModel
{
    Q_OBJECT

public:
    enum Column {
        ID = 0,
        TYPE,
        LONGITUDE,
        LATITUDE,
        ALTITUDE,
        SPEED,
        HEADING,
        STATUS,
        COLUMN_COUNT
    };

    explicit AircraftModel(QObject *parent = nullptr);

    // QAbstractTableModel interface
    int rowCount(const QModelIndex &parent = QModelIndex()) const override;
    int columnCount(const QModelIndex &parent = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int role = Qt::DisplayRole) const override;
    QVariant headerData(int section, Qt::Orientation orientation, int role = Qt::DisplayRole) const override;
    bool setData(const QModelIndex &index, const QVariant &value, int role = Qt::EditRole) override;
    Qt::ItemFlags flags(const QModelIndex &index) const override;

    // Custom methods
    void addAircraft(const Aircraft &aircraft);
    void removeAircraft(int row);
    void clearAircraft();
    QList<Aircraft> getAircraftList() const;
    void setAircraftList(const QList<Aircraft> &aircraftList);
    Aircraft getAircraft(int row) const;

private:
    QList<Aircraft> m_aircraftList;
    QStringList m_headers;
};

#endif // AIRCRAFTMODEL_H
