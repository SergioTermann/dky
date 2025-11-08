#include "aircraftmodel.h"
#include <QColor>
#include <QMessageBox>
#include <QDoubleValidator>
#include <QLocale>
#include <QRegExp>

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
    case ID: 
        aircraft.id = value.toInt(); 
        break;
    case TYPE: 
        aircraft.type = value.toString(); 
        break;
    case LONGITUDE: {
        // 验证经度输入
        QString strValue = value.toString().trimmed();
        
        // 检查是否为空
        if (strValue.isEmpty()) {
            QMessageBox::warning(nullptr, "输入错误", "经度不能为空！\n请输入有效的经度值（-180 到 180）");
            return false;
        }
        
        // 检查是否包含非数字字符（允许负号、小数点）
        QRegExp regex("^-?\\d+(\\.\\d+)?$");
        if (!regex.exactMatch(strValue)) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("经度只能输入数字！\n您输入的值：%1\n请输入有效的经度值（-180 到 180）").arg(strValue));
            return false;
        }
        
        // 转换为double并验证范围
        bool ok;
        double longitude = strValue.toDouble(&ok);
        if (!ok) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("经度格式错误！\n您输入的值：%1\n请输入有效的经度值（-180 到 180）").arg(strValue));
            return false;
        }
        
        // 验证经度范围：-180 到 180
        if (longitude < -180.0 || longitude > 180.0) {
            QMessageBox::warning(nullptr, "范围错误", 
                QString("经度超出有效范围！\n您输入的值：%1\n有效范围：-180 到 180").arg(longitude));
            return false;
        }
        
        aircraft.longitude = longitude;
        break;
    }
    case LATITUDE: {
        // 验证纬度输入
        QString strValue = value.toString().trimmed();
        
        // 检查是否为空
        if (strValue.isEmpty()) {
            QMessageBox::warning(nullptr, "输入错误", "纬度不能为空！\n请输入有效的纬度值（-90 到 90）");
            return false;
        }
        
        // 检查是否包含非数字字符（允许负号、小数点）
        QRegExp regex("^-?\\d+(\\.\\d+)?$");
        if (!regex.exactMatch(strValue)) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("纬度只能输入数字！\n您输入的值：%1\n请输入有效的纬度值（-90 到 90）").arg(strValue));
            return false;
        }
        
        // 转换为double并验证范围
        bool ok;
        double latitude = strValue.toDouble(&ok);
        if (!ok) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("纬度格式错误！\n您输入的值：%1\n请输入有效的纬度值（-90 到 90）").arg(strValue));
            return false;
        }
        
        // 验证纬度范围：-90 到 90
        if (latitude < -90.0 || latitude > 90.0) {
            QMessageBox::warning(nullptr, "范围错误", 
                QString("纬度超出有效范围！\n您输入的值：%1\n有效范围：-90 到 90").arg(latitude));
            return false;
        }
        
        aircraft.latitude = latitude;
        break;
    }
    case ALTITUDE: {
        // 验证高度输入
        QString strValue = value.toString().trimmed();
        
        // 检查是否为空
        if (strValue.isEmpty()) {
            QMessageBox::warning(nullptr, "输入错误", "高度不能为空！\n请输入有效的数字");
            return false;
        }
        
        // 检查是否包含非数字字符（允许小数点，不允许负号）
        QRegExp regex("^\\d+(\\.\\d+)?$");
        if (!regex.exactMatch(strValue)) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("高度只能输入数字（不能为负数）！\n您输入的值：%1\n请输入有效的数字").arg(strValue));
            return false;
        }
        
        // 转换为double并验证
        bool ok;
        double altitude = strValue.toDouble(&ok);
        if (!ok) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("高度格式错误！\n您输入的值：%1\n请输入有效的数字").arg(strValue));
            return false;
        }
        
        aircraft.altitude = altitude;
        break;
    }
    case SPEED: {
        // 验证速度输入
        QString strValue = value.toString().trimmed();
        
        // 检查是否为空
        if (strValue.isEmpty()) {
            QMessageBox::warning(nullptr, "输入错误", "速度不能为空！\n请输入有效的数字");
            return false;
        }
        
        // 检查是否包含非数字字符（允许小数点，不允许负号）
        QRegExp regex("^\\d+(\\.\\d+)?$");
        if (!regex.exactMatch(strValue)) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("速度只能输入数字（不能为负数）！\n您输入的值：%1\n请输入有效的数字").arg(strValue));
            return false;
        }
        
        // 转换为double并验证
        bool ok;
        double speed = strValue.toDouble(&ok);
        if (!ok) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("速度格式错误！\n您输入的值：%1\n请输入有效的数字").arg(strValue));
            return false;
        }
        
        aircraft.speed = speed;
        break;
    }
    case HEADING: {
        // 验证航向输入
        QString strValue = value.toString().trimmed();
        
        // 检查是否为空
        if (strValue.isEmpty()) {
            QMessageBox::warning(nullptr, "输入错误", "航向不能为空！\n请输入有效的航向值（0 到 360）");
            return false;
        }
        
        // 检查是否包含非数字字符（允许小数点，航向不能为负数）
        QRegExp regex("^\\d+(\\.\\d+)?$");
        if (!regex.exactMatch(strValue)) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("航向只能输入数字！\n您输入的值：%1\n请输入有效的航向值（0 到 360）").arg(strValue));
            return false;
        }
        
        // 转换为double并验证范围
        bool ok;
        double heading = strValue.toDouble(&ok);
        if (!ok) {
            QMessageBox::warning(nullptr, "输入错误", 
                QString("航向格式错误！\n您输入的值：%1\n请输入有效的航向值（0 到 360）").arg(strValue));
            return false;
        }
        
        // 验证航向范围：0 到 360
        if (heading < 0.0 || heading > 360.0) {
            QMessageBox::warning(nullptr, "范围错误", 
                QString("航向超出有效范围！\n您输入的值：%1\n有效范围：0 到 360").arg(heading));
            return false;
        }
        
        aircraft.heading = heading;
        break;
    }
    case STATUS: 
        aircraft.status = value.toString(); 
        break;
    default: 
        return false;
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
