#include "aircraftmodel.h"
#include <QColor>

AircraftModel::AircraftModel(QObject *parent)
    : QAbstractTableModel(parent)
{
    m_headers << "ID" << "类型" << "经度" << "纬度" << "高度" << "速度" << "航向" << "状态";
}

int AircraftModel::rowCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent)
    return m_aircraftList.size();
}

int AircraftModel::columnCount(const QModelIndex &parent) const
{
    Q_UNUSED(parent)
    return COLUMN_COUNT;
}

QVariant AircraftModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_aircraftList.size())
        return QVariant();

    const Aircraft &aircraft = m_aircraftList.at(index.row());

    if (role == Qt::DisplayRole || role == Qt::EditRole) {
        switch (index.column()) {
        case ID: return aircraft.id;
        case TYPE: return aircraft.type;
        case LONGITUDE: return QString::number(aircraft.longitude, 'f', 6);
        case LATITUDE: return QString::number(aircraft.latitude, 'f', 6);
        case ALTITUDE: return QString::number(aircraft.altitude, 'f', 2);
        case SPEED: return QString::number(aircraft.speed, 'f', 2);
        case HEADING: return QString::number(aircraft.heading, 'f', 2);
        case STATUS: return aircraft.status;
        }
    }

    return QVariant();
}

QVariant AircraftModel::headerData(int section, Qt::Orientation orientation, int role) const
{
    if (orientation == Qt::Horizontal && role == Qt::DisplayRole) {
        if (section < m_headers.size())
            return m_headers.at(section);
    }
    return QVariant();
}

bool AircraftModel::setData(const QModelIndex &index, const QVariant &value, int role)
{
    if (!index.isValid() || index.row() >= m_aircraftList.size() || role != Qt::EditRole)
        return false;

    Aircraft &aircraft = m_aircraftList[index.row()];

    switch (index.column()) {
    case ID: aircraft.id = value.toInt(); break;
    case TYPE: aircraft.type = value.toString(); break;
    case LONGITUDE: aircraft.longitude = value.toDouble(); break;
    case LATITUDE: aircraft.latitude = value.toDouble(); break;
    case ALTITUDE: aircraft.altitude = value.toDouble(); break;
    case SPEED: aircraft.speed = value.toDouble(); break;
    case HEADING: aircraft.heading = value.toDouble(); break;
    case STATUS: aircraft.status = value.toString(); break;
    default: return false;
    }

    emit dataChanged(index, index);
    return true;
}

Qt::ItemFlags AircraftModel::flags(const QModelIndex &index) const
{
    if (!index.isValid())
        return Qt::NoItemFlags;

    return Qt::ItemIsEnabled | Qt::ItemIsSelectable | Qt::ItemIsEditable;
}

void AircraftModel::addAircraft(const Aircraft &aircraft)
{
    beginInsertRows(QModelIndex(), m_aircraftList.size(), m_aircraftList.size());
    m_aircraftList.append(aircraft);
    endInsertRows();
}

void AircraftModel::removeAircraft(int row)
{
    if (row >= 0 && row < m_aircraftList.size()) {
        beginRemoveRows(QModelIndex(), row, row);
        m_aircraftList.removeAt(row);
        endRemoveRows();
    }
}

void AircraftModel::clearAircraft()
{
    beginResetModel();
    m_aircraftList.clear();
    endResetModel();
}

QList<Aircraft> AircraftModel::getAircraftList() const
{
    return m_aircraftList;
}

void AircraftModel::setAircraftList(const QList<Aircraft> &aircraftList)
{
    beginResetModel();
    m_aircraftList = aircraftList;
    endResetModel();
}

Aircraft AircraftModel::getAircraft(int row) const
{
    if (row >= 0 && row < m_aircraftList.size())
        return m_aircraftList.at(row);
    return Aircraft();
}
