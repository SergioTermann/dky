#ifndef MAINWINDOW_H
#define MAINWINDOW_H

#include <QMainWindow>
#include <QFileDialog>
#include <QMessageBox>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QStatusBar>
#include <QLabel>
#include <QTimer>
#include <QDateTime>
#include <QTextStream>
#include <QScrollBar>
#include <QProcess>
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include "aircraftmodel.h"
#include "situationgenerator.h"

// 项目根目录常量定义
const QString PROJECT_ROOT_DIR = "D:/DKY2/dky/dky/";

QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class MainWindow : public QMainWindow
{
    Q_OBJECT

public:
    MainWindow(QWidget *parent = nullptr);
    ~MainWindow();

private slots:
    // 界面按钮槽函数
    void on_addRedAircraftButton_clicked();
    void on_removeRedAircraftButton_clicked();
    void on_generateButton_clicked();
    void on_actionLoadRed_triggered();
    void on_actionSave_triggered();
    void on_clearRedButton_clicked();
    void on_clearBlueButton_clicked();
    void on_clearLogButton_clicked();
    void on_startSimulationButton_clicked();
    void on_pauseResumeButton_clicked();
    void on_speedComboBox_currentIndexChanged(int index);
    void on_blueModeComboBox_currentIndexChanged(int index);
    void on_onlineDebugButton_clicked();
    void on_killAllProcessesButton_clicked();

    // 菜单栏槽函数
    void on_actionExit_triggered();
    void on_actionToggleLog_triggered();
    void on_actionZoomIn_triggered();
    void on_actionZoomOut_triggered();
    void on_actionResetZoom_triggered();
    void on_actionAbout_triggered();
    void on_actionManual_triggered();

    // 数据模型变化响应
    void updateRedStatistics();
    void updateBlueStatistics();
    void updateStatusBar();
    
    // 态势评分计算
    void updateSituationScores();
    int calculateRedScore();
    int calculateBlueScore();

private:
    void initializeModels();
    void initializeData();
    void initializeUI();
    void connectSignals();

    // 日志系统
    void addLogMessage(const QString &message, const QString &level = "INFO");
    void updateLogCount();

    // UI更新
    void updateRecommendationLabels(int count, const QString &strategy);
    void clearRecommendationLabels();

    // 视图控制
    void setZoomFactor(double factor);
    // 事件过滤器
    bool eventFilter(QObject *obj, QEvent *event) override;
    Ui::MainWindow *ui;

    // Data models
    AircraftModel *redAircraftModel;
    AircraftModel *blueAircraftModel;

    // UI元素
    QLabel *statusLabel;
    QLabel *redCountStatusLabel;
    QLabel *blueCountStatusLabel;
    QLabel *timeLabel;
    QTimer *timeUpdateTimer;

    // 状态变量
    int nextAircraftId;
    int logMessageCount;
    double currentZoomFactor;
    
    // 推演控制变量
    bool isPaused;
    double speedMultiplier;
    QString controlFilePath;
    
    // Python进程管理
    QProcess *pythonProcess;
    
    // 辅助函数
    void updateSimulationControlFile();
    void enableSimulationControls(bool enable);
    void createPythonDebugScript(const QString &scriptPath);
};

#endif // MAINWINDOW_H
