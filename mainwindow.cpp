#include "mainwindow.h"
#include "ui_mainwindow.h"
#include <QHeaderView>
#include <QSplitter>
#include <QMouseEvent>
#include <QEvent>

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
    , nextAircraftId(1)
    , logMessageCount(0)
    , currentZoomFactor(1.0)
    , isPaused(false)
    , speedMultiplier(1.0)
    , pythonProcess(nullptr)
{
    ui->setupUi(this);
    
    // 设置控制文件路径（使用项目源码目录）
    controlFilePath = PROJECT_ROOT_DIR + "simulation_control.json";
    
    initializeModels();
    initializeData();
    initializeUI();
    connectSignals();

    // 欢迎日志
    addLogMessage("系统启动完成，动态场景生成平台就绪", "INFO");
    
    // 设置红蓝双方任务模式下拉框默认值为攻击（阻断信号避免初始化时输出日志）
    ui->redModeComboBox->blockSignals(true);
    ui->redModeComboBox->setCurrentIndex(0);
    ui->redModeComboBox->blockSignals(false);
    
    ui->blueModeComboBox->blockSignals(true);
    ui->blueModeComboBox->setCurrentIndex(0);
    ui->blueModeComboBox->blockSignals(false);
    
    // 设置倍速下拉框默认值为1x（阻断信号避免初始化时输出日志）
    ui->speedComboBox->blockSignals(true);
    ui->speedComboBox->setCurrentIndex(1);
    ui->speedComboBox->blockSignals(false);
    
    // 初始化控制文件（不输出日志）
    updateSimulationControlFile(false);
    
    addLogMessage(QString("控制文件路径：%1").arg(controlFilePath), "INFO");
}

MainWindow::~MainWindow()
{
    // 清理Python进程
    if (pythonProcess) {
        pythonProcess->kill();
        pythonProcess->deleteLater();
        pythonProcess = nullptr;
    }
    
    delete ui;
}

void MainWindow::initializeModels()
{
    // 初始化红方数据模型
    redAircraftModel = new AircraftModel(this);
    ui->redTableView->setModel(redAircraftModel);
    ui->redTableView->setSelectionBehavior(QAbstractItemView::SelectRows);
    ui->redTableView->horizontalHeader()->setStretchLastSection(true);

    // 初始化蓝方数据模型
    blueAircraftModel = new AircraftModel(this);
    ui->blueTableView->setModel(blueAircraftModel);
    ui->blueTableView->setSelectionBehavior(QAbstractItemView::SelectRows);
    ui->blueTableView->horizontalHeader()->setStretchLastSection(true);

    // 初始化策略下拉框
    ui->strategyComboBox->addItem(""); // 空选项
    ui->strategyComboBox->addItems({"简单", "中等", "困难"});

    // 设置蓝方数量范围
    ui->blueAircraftCountSpinBox->setRange(0, 100);
    ui->blueAircraftCountSpinBox->setValue(0);
}

void MainWindow::initializeData()
{
    nextAircraftId = 1;

    // 清空推荐标签
    clearRecommendationLabels();
}

void MainWindow::initializeUI()
{
    // 设置窗口标题和图标
    setWindowTitle("动态场景生成平台");

    // 初始化状态栏
    statusLabel = new QLabel("系统就绪");
    redCountStatusLabel = new QLabel("红方: 0架");
    blueCountStatusLabel = new QLabel("蓝方: 0架");
    timeLabel = new QLabel();

    ui->statusbar->addWidget(statusLabel);
    ui->statusbar->addPermanentWidget(redCountStatusLabel);
    ui->statusbar->addPermanentWidget(blueCountStatusLabel);
    ui->statusbar->addPermanentWidget(timeLabel);

    // 设置时间更新定时器
    timeUpdateTimer = new QTimer(this);
    connect(timeUpdateTimer, &QTimer::timeout, this, &MainWindow::updateStatusBar);
    timeUpdateTimer->start(1000); // 每秒更新一次
    // 安装事件过滤器，用于处理点击空白处清除选择
    ui->redTableView->viewport()->installEventFilter(this);
    ui->blueTableView->viewport()->installEventFilter(this);

    // 初始状态更新
    updateRedStatistics();
    updateBlueStatistics();
    updateStatusBar();
    updateLogCount();
}

void MainWindow::connectSignals()
{
    // 连接数据模型信号
    connect(redAircraftModel, &AircraftModel::rowsInserted, this, &MainWindow::updateRedStatistics);
    connect(redAircraftModel, &AircraftModel::rowsRemoved, this, &MainWindow::updateRedStatistics);
    connect(redAircraftModel, &AircraftModel::modelReset, this, &MainWindow::updateRedStatistics);

    connect(blueAircraftModel, &AircraftModel::rowsInserted, this, &MainWindow::updateBlueStatistics);
    connect(blueAircraftModel, &AircraftModel::rowsRemoved, this, &MainWindow::updateBlueStatistics);
    connect(blueAircraftModel, &AircraftModel::modelReset, this, &MainWindow::updateBlueStatistics);
}

// ================== 界面按钮槽函数 ==================

void MainWindow::on_addRedAircraftButton_clicked()
{
    Aircraft newAircraft(nextAircraftId++, "新飞机", 0.0, 0.0, 5000, 500, 0, "待命");
    redAircraftModel->addAircraft(newAircraft);
    addLogMessage(QString("添加红方飞机 ID:%1").arg(newAircraft.id), "INFO");
}

void MainWindow::on_removeRedAircraftButton_clicked()
{
    QModelIndexList selected = ui->redTableView->selectionModel()->selectedRows();
    if (!selected.isEmpty()) {
        int row = selected.first().row();
        Aircraft aircraft = redAircraftModel->getAircraft(row);
        redAircraftModel->removeAircraft(row);
        addLogMessage(QString("删除红方飞机 ID:%1").arg(aircraft.id), "INFO");
    } else {
        QMessageBox::information(this, "提示", "请先选择要删除的行");
        addLogMessage("删除操作失败：未选择飞机", "WARN");
    }
}

void MainWindow::on_generateButton_clicked()
{
    addLogMessage("开始生成蓝方态势...", "INFO");

    // 获取红方态势数据
    QList<Aircraft> redAircraftList = redAircraftModel->getAircraftList();
    if (redAircraftList.isEmpty()) {
        QMessageBox::warning(this, "警告", "请先添加红方态势数据");
        addLogMessage("生成失败：红方态势数据为空", "ERROR");
        return;
    }

    // 选择保存文件的位置
    QString fileName = QFileDialog::getSaveFileName(this,
                                                    "保存态势文件",
                                                    QDir::currentPath() + "/situation.json",
                                                    "JSON Files (*.json);;XML Files (*.xml)");

    if (fileName.isEmpty()) {
        addLogMessage("用户取消了文件保存操作", "INFO");
        return;
    }

    // 记录开始时间（从文件对话框返回后开始计时）
    QElapsedTimer timer;
    timer.start();

    // 获取用户设置的参数
    int userBlueCount = ui->blueAircraftCountSpinBox->value();
    QString userStrategy = ui->strategyComboBox->currentText();

    // 如果用户没有设置，传递默认值让算法自动计算
    int algorithmBlueCount = (userBlueCount > 0) ? userBlueCount : -1;
    QString algorithmStrategy = (!userStrategy.isEmpty()) ? userStrategy : "";

    addLogMessage(QString("算法参数 - 数量:%1, 难度:%2")
                      .arg(algorithmBlueCount == -1 ? "自动" : QString::number(algorithmBlueCount))
                      .arg(algorithmStrategy.isEmpty() ? "自动" : algorithmStrategy), "INFO");

    // 调用算法生成态势文件
    SituationGenerator::GenerationResult result =
        SituationGenerator::generateBlueSituation(redAircraftList, algorithmBlueCount, algorithmStrategy);

    // 界面更新，显示算法计算的参数
    updateRecommendationLabels(result.recommendedBlueCount, result.recommendedStrategy);

    if (userBlueCount <= 0) {
        ui->blueAircraftCountSpinBox->setValue(result.recommendedBlueCount);
    }
    if (userStrategy.isEmpty()) {
        int index = ui->strategyComboBox->findText(result.recommendedStrategy);
        if (index >= 0) {
            ui->strategyComboBox->setCurrentIndex(index);
        }
    }

    // 清空当前蓝方数据并设置新数据
    blueAircraftModel->clearAircraft();
    blueAircraftModel->setAircraftList(result.blueAircraftList);
    // 确定最终使用的策略和数量（优先使用用户选择的，否则使用算法推荐的）
    QString finalStrategy = (!userStrategy.isEmpty()) ? userStrategy : result.recommendedStrategy;
    int finalBlueCount = (userBlueCount > 0) ? userBlueCount : result.recommendedBlueCount;
    
    // 保存其他参数
    QJsonObject params;
    params["blue_count"] = finalBlueCount;
    params["strategy"] = finalStrategy;
    
    // 根据文件扩展名选择保存格式
    bool saveSuccess = false;
    if (fileName.endsWith(".xml", Qt::CaseInsensitive)) {
        // 保存为XML格式
        saveSuccess = saveToXml(fileName, redAircraftList, result.blueAircraftList, params);
    } else {
        // 保存为JSON格式（默认）
        QJsonObject rootObj;
        
        // 红方数据
        QJsonArray redArray;
        for (const auto& aircraft : redAircraftList) {
            redArray.append(aircraft.toJson());
        }
        rootObj["red_aircraft"] = redArray;

        // 蓝方数据
        QJsonArray blueArray;
        for (const auto& aircraft : result.blueAircraftList) {
            blueArray.append(aircraft.toJson());
        }
        rootObj["blue_aircraft"] = blueArray;
        rootObj["parameters"] = params;

        QJsonDocument doc(rootObj);

        QFile file(fileName);
        if (file.open(QIODevice::WriteOnly)) {
            file.write(doc.toJson());
            file.close();
            saveSuccess = true;
        }
    }
    
    if (!saveSuccess) {
        QMessageBox::critical(this, "错误", "无法创建文件");
        addLogMessage(QString("态势文件保存失败：%1").arg(fileName), "ERROR");
        return;
    }
    
    // 记录结束时间并计算耗时
    qint64 elapsedMs = timer.elapsed();  // 计算毫秒数
    double elapsedSeconds = elapsedMs / 1000.0;   // 转换为秒
    
    // 格式化耗时显示
    QString elapsedStr;
    if (elapsedSeconds < 1.0) {
        elapsedStr = QString("%1 毫秒").arg(elapsedMs);
    } else if (elapsedSeconds < 60.0) {
        elapsedStr = QString("%1 秒").arg(elapsedSeconds, 0, 'f', 3);
    } else {
        int minutes = static_cast<int>(elapsedSeconds / 60);
        double seconds = elapsedSeconds - minutes * 60;
        elapsedStr = QString("%1 分 %2 秒").arg(minutes).arg(seconds, 0, 'f', 3);
    }
    
    addLogMessage(QString("生成态势文件耗时：%1").arg(elapsedStr), "INFO");
    addLogMessage(QString("成功生成%1架蓝方飞机，难度：%2，已保存到文件：%3")
                      .arg(result.blueAircraftList.size())
                      .arg(finalStrategy)
                      .arg(fileName), "SUCCESS");

    QMessageBox::information(this, "成功",
                             QString("已生成%1架蓝方飞机，难度：%2\n态势文件已保存到：%3\n耗时：%4")
                                 .arg(result.blueAircraftList.size())
                                 .arg(finalStrategy)
                                 .arg(fileName)
                                 .arg(elapsedStr));
}

void MainWindow::on_actionLoadRed_triggered()
{
    QString fileName = QFileDialog::getOpenFileName(this,
                                                    "加载红方态势",
                                                    QDir::currentPath() + "/test_red_data.json",
                                                    "All Supported Files (*.json *.xml);;JSON Files (*.json);;XML Files (*.xml)");

    if (fileName.isEmpty()) return;

    QList<Aircraft> aircraftList;
    QJsonObject params;
    bool loadSuccess = false;
    
    // 根据文件扩展名选择加载格式
    if (fileName.endsWith(".xml", Qt::CaseInsensitive)) {
        // 从XML文件加载
        loadSuccess = loadFromXml(fileName, aircraftList, params);
        if (!loadSuccess) {
            QMessageBox::critical(this, "错误", "无法解析XML文件");
            addLogMessage(QString("XML文件解析失败：%1").arg(fileName), "ERROR");
            return;
        }
    } else {
        // 从JSON文件加载
        QFile file(fileName);
        if (!file.open(QIODevice::ReadOnly)) {
            QMessageBox::critical(this, "错误", "无法打开文件");
            addLogMessage(QString("文件加载失败：%1").arg(fileName), "ERROR");
            return;
        }

        QByteArray data = file.readAll();
        QJsonDocument doc = QJsonDocument::fromJson(data);

        QJsonArray array;

        // 支持两种格式：纯数组格式 或 包含red_aircraft的对象格式
        if (doc.isArray()) {
            // 格式1: 纯数组 [{...}, {...}]
            array = doc.array();
        } else if (doc.isObject()) {
            // 格式2: 对象格式 {"red_aircraft": [...], "blue_aircraft": [...]}
            QJsonObject obj = doc.object();
            if (obj.contains("red_aircraft") && obj["red_aircraft"].isArray()) {
                array = obj["red_aircraft"].toArray();
                
                // 加载参数
                if (obj.contains("parameters") && obj["parameters"].isObject()) {
                    params = obj["parameters"].toObject();
                }
            } else {
                QMessageBox::critical(this, "错误", "找不到red_aircraft字段");
                addLogMessage("加载失败：找不到red_aircraft字段", "ERROR");
                return;
            }
        } else {
            QMessageBox::critical(this, "错误", "JSON格式错误");
            addLogMessage("加载失败：JSON格式错误", "ERROR");
            return;
        }

        for (const auto& value : array) {
            if (value.isObject()) {
                Aircraft aircraft = Aircraft::fromJson(value.toObject());
                aircraftList.append(aircraft);
            }
        }
        loadSuccess = true;
    }
    
    // 加载任务模式（如果存在）
    if (params.contains("task_mode")) {
        QString taskMode = params["task_mode"].toString();
        int redModeIndex = 0; // 默认为攻击模式
        int blueModeIndex = 1; // 蓝方默认为防御模式（与红方相反）
        
        if (taskMode == "attack") {
            redModeIndex = 0;  // 红方：攻击
            blueModeIndex = 1; // 蓝方：防御（相反）
        } else if (taskMode == "defense") {
            redModeIndex = 1; // 红方：防御
            blueModeIndex = 0; // 蓝方：攻击（相反）
        } else if (taskMode == "confrontation") {
            redModeIndex = 2; // 红方：对抗
            blueModeIndex = 2; // 蓝方：对抗（对抗模式保持相同）
        }
        
        // 设置任务模式（阻断信号避免触发不必要的日志）
        ui->redModeComboBox->blockSignals(true);
        ui->blueModeComboBox->blockSignals(true);
        ui->redModeComboBox->setCurrentIndex(redModeIndex);
        ui->blueModeComboBox->setCurrentIndex(blueModeIndex);
        ui->redModeComboBox->blockSignals(false);
        ui->blueModeComboBox->blockSignals(false);
        
        // 更新控制文件（静默更新，不输出日志）
        updateSimulationControlFile(false);
    }

    redAircraftModel->setAircraftList(aircraftList);

    // 更新nextAircraftId
    int maxId = 0;
    for (const auto& aircraft : aircraftList) {
        if (aircraft.id > maxId) maxId = aircraft.id;
    }
    nextAircraftId = maxId + 1;

    addLogMessage(QString("成功加载%1架红方飞机").arg(aircraftList.size()), "SUCCESS");
    QMessageBox::information(this, "成功", QString("已加载%1架红方飞机").arg(aircraftList.size()));
}

void MainWindow::on_actionSave_triggered()
{
    QList<Aircraft> redList = redAircraftModel->getAircraftList();
    QList<Aircraft> blueList = blueAircraftModel->getAircraftList();

    if (redList.isEmpty() && blueList.isEmpty()) {
        QMessageBox::information(this, "提示", "没有数据可保存");
        addLogMessage("保存操作取消：无数据可保存", "WARN");
        return;
    }

    QString fileName = QFileDialog::getSaveFileName(this,
                                                    "保存态势数据",
                                                    QDir::currentPath() + "/test_red_blue_data.json",
                                                    "JSON Files (*.json);;XML Files (*.xml)");

    if (fileName.isEmpty()) return;

    // 保存其他参数
    QJsonObject params;
    params["blue_count"] = ui->blueAircraftCountSpinBox->value();
    params["strategy"] = ui->strategyComboBox->currentText();
    
    // 保存任务模式
    QString taskMode;
    switch (ui->redModeComboBox->currentIndex()) {
        case 0:
            taskMode = "attack";
            break;
        case 1:
            taskMode = "defense";
            break;
        case 2:
            taskMode = "confrontation";
            break;
        default:
            taskMode = "attack";
    }
    params["task_mode"] = taskMode;
    
    // 根据文件扩展名选择保存格式
    bool saveSuccess = false;
    if (fileName.endsWith(".xml", Qt::CaseInsensitive)) {
        // 保存为XML格式
        saveSuccess = saveToXml(fileName, redList, blueList, params);
    } else {
        // 保存为JSON格式（默认）
        QJsonObject rootObj;

        // 红方数据
        QJsonArray redArray;
        for (const auto& aircraft : redList) {
            redArray.append(aircraft.toJson());
        }
        rootObj["red_aircraft"] = redArray;

        // 蓝方数据
        QJsonArray blueArray;
        for (const auto& aircraft : blueList) {
            blueArray.append(aircraft.toJson());
        }
        rootObj["blue_aircraft"] = blueArray;
        rootObj["parameters"] = params;

        QJsonDocument doc(rootObj);

        QFile file(fileName);
        if (file.open(QIODevice::WriteOnly)) {
            file.write(doc.toJson());
            file.close();
            saveSuccess = true;
        }
    }
    
    if (!saveSuccess) {
        QMessageBox::critical(this, "错误", "无法创建文件");
        addLogMessage(QString("文件保存失败：%1").arg(fileName), "ERROR");
        return;
    }

    QString modeText = ui->redModeComboBox->currentText();
    addLogMessage(QString("数据保存成功：红方%1架，蓝方%2架，任务模式：%3").arg(redList.size()).arg(blueList.size()).arg(modeText), "SUCCESS");
    QMessageBox::information(this, "成功",
                             QString("已保存%1架红方飞机，%2架蓝方飞机\n任务模式：%3").arg(redList.size()).arg(blueList.size()).arg(modeText));
}

void MainWindow::on_clearRedButton_clicked()
{
    if (redAircraftModel->getAircraftList().isEmpty()) {
        addLogMessage("清空操作：红方表格已为空", "INFO");
        return;
    }

    int count = redAircraftModel->getAircraftList().size();
    redAircraftModel->clearAircraft();
    addLogMessage(QString("清空红方表格：删除%1架飞机").arg(count), "INFO");

    // 清空推荐信息
    clearRecommendationLabels();
}

void MainWindow::on_clearBlueButton_clicked()
{
    if (blueAircraftModel->getAircraftList().isEmpty()) {
        addLogMessage("清空操作：蓝方表格已为空", "INFO");
        return;
    }

    int count = blueAircraftModel->getAircraftList().size();
    blueAircraftModel->clearAircraft();
    addLogMessage(QString("清空蓝方表格：删除%1架飞机").arg(count), "INFO");
}

void MainWindow::on_clearLogButton_clicked()
{
    ui->logTextEdit->clear();
    logMessageCount = 0;
    updateLogCount();
    addLogMessage("日志已清空", "INFO");
}

void MainWindow::on_startSimulationButton_clicked()
{
    // 启用推演控制按钮并初始化控制文件
    enableSimulationControls(true);
    updateSimulationControlFile();
    
    // 直接运行 task_allocation.py
    addLogMessage("启动 Python 推演程序", "INFO");

    // 使用项目源码目录的 Python 脚本
    QString pythonScriptPath = PROJECT_ROOT_DIR + "task_allocation.py";
    
    if (!QFile::exists(pythonScriptPath)) {
        QMessageBox::critical(this, "错误", 
            QString("找不到Python脚本：%1").arg(pythonScriptPath));
        addLogMessage("找不到Python脚本文件", "ERROR");
        enableSimulationControls(false);
        return;
    }
    
    // 工作目录设置为项目源码目录
    QString workDir = QString(PROJECT_ROOT_DIR).replace("\\", "/");
    if (workDir.endsWith("/")) {
        workDir.chop(1);  // 去掉末尾的斜杠
    }
    
    // 直接运行 task_allocation.py
    // 使用 start 命令在新窗口中运行，这样可以正确激活conda环境
    QString command = QString("start \"Python Simulation\" /D \"%1\" cmd /K \"conda activate ppoa && python -u \"%2\"\"")
                      .arg(workDir)
                      .arg(pythonScriptPath);
    
    addLogMessage(QString("执行Python脚本：%1").arg(pythonScriptPath), "INFO");
    addLogMessage(QString("工作目录：%1").arg(workDir), "INFO");
    
    // 使用 system() 执行 start 命令（Windows 最可靠的方式）
    int result = system(command.toLocal8Bit().constData());
    
    if (result == 0) {
        addLogMessage("✓ Python脚本已在新窗口中启动", "SUCCESS");
    } else {
        addLogMessage(QString("启动失败 (返回码: %1)").arg(result), "ERROR");
        QMessageBox::critical(this, "错误", "无法启动Python脚本");
        enableSimulationControls(false);
        return;
    }
}

// ================== 菜单栏槽函数 ==================

void MainWindow::on_actionExit_triggered()
{
    close();
}

void MainWindow::on_actionToggleLog_triggered()
{
    bool visible = ui->actionToggleLog->isChecked();
    ui->logGroupBox->setVisible(visible);
    addLogMessage(visible ? "显示日志面板" : "隐藏日志面板", "INFO");
}

void MainWindow::on_actionZoomIn_triggered()
{
    double newFactor = currentZoomFactor * 1.1;
    setZoomFactor(newFactor);
    addLogMessage(QString("界面放大：%1%").arg(qRound(currentZoomFactor * 100)), "INFO");
}

void MainWindow::on_actionZoomOut_triggered()
{
    double newFactor = currentZoomFactor * 0.9;
    setZoomFactor(newFactor);
    addLogMessage(QString("界面缩小：%1%").arg(qRound(currentZoomFactor * 100)), "INFO");
}

void MainWindow::on_actionResetZoom_triggered()
{
    setZoomFactor(1.0);
    addLogMessage("重置界面缩放：100%", "INFO");
}

void MainWindow::on_actionAbout_triggered()
{
    QMessageBox::about(this, "关于",
                       "动态场景生成平台 v1.0\n\n"
                       "功能特性：\n"
                       "• 红方态势管理\n"
                       "• 智能蓝方生成\n"
                       "• 数据导入导出\n"
                       "• 实时操作日志\n\n"
                       "开发日期：2025年8月1日");
}

void MainWindow::on_actionManual_triggered()
{
    QMessageBox::information(this, "使用手册",
                             "使用说明：\n\n"
                             "1. 红方态势管理：\n"
                             "   - 点击'添加飞机'创建新的红方单位\n"
                             "   - 选中行后点击'删除'移除单位\n"
                             "   - 双击表格单元格可直接编辑\n\n"
                             "2. 态势生成与推演：\n"
                             "   - 设置数量和难度，或留空使用算法推荐\n"
                             "   - 点击'生成态势文件'生成红蓝态势\n"
                             "   - 点击'开始推演'执行态势推演\n\n"
                             "3. 文件操作：\n"
                             "   - 文件菜单可加载/保存态势数据\n\n"
                             "4. 快捷键：\n"
                             "   - Ctrl+O: 加载文件\n"
                             "   - Ctrl+S: 保存文件\n"
                             "   - Ctrl+L: 切换日志面板\n"
                             "   - F1: 显示此帮助");
}

// ================== 统计和UI更新函数 ==================

void MainWindow::updateRedStatistics()
{
    int count = redAircraftModel->getAircraftList().size();
    ui->redCountLabel->setText(QString("📊 总数: %1架").arg(count));
    redCountStatusLabel->setText(QString("红方: %1架").arg(count));
    
    // 更新红方评分
    int score = calculateRedScore();
    ui->redScoreLabel->setText(QString("⭐ 评分: %1").arg(score));
}

void MainWindow::updateBlueStatistics()
{
    int count = blueAircraftModel->getAircraftList().size();
    ui->blueCountDisplayLabel->setText(QString("📊 总数: %1架").arg(count));
    blueCountStatusLabel->setText(QString("蓝方: %1架").arg(count));
    
    // 更新蓝方评分
    int score = calculateBlueScore();
    ui->blueScoreLabel->setText(QString("⭐ 评分: %1").arg(score));
}

void MainWindow::updateStatusBar()
{
    // 更新时间
    timeLabel->setText(QDateTime::currentDateTime().toString("hh:mm:ss"));
}

void MainWindow::updateRecommendationLabels(int count, const QString &strategy)
{
    ui->recommendCountLabel->setText(QString("• 建议数量: %1架").arg(count));
    ui->recommendStrategyLabel->setText(QString("• 建议策略: %1").arg(strategy));
}

void MainWindow::clearRecommendationLabels()
{
    ui->recommendCountLabel->setText("• 建议数量: 待计算");
    ui->recommendStrategyLabel->setText("• 建议策略: 待计算");
}

// ================== 日志系统 ==================

void MainWindow::addLogMessage(const QString &message, const QString &level)
{
    QString timestamp = QDateTime::currentDateTime().toString("hh:mm:ss");
    QString coloredMessage;

    if (level == "ERROR") {
        coloredMessage = QString("<span style='color: #E53E3E;'>%1 [错误] %2</span>").arg(timestamp, message);
    } else if (level == "WARN") {
        coloredMessage = QString("<span style='color: #D69E2E;'>%1 [警告] %2</span>").arg(timestamp, message);
    } else if (level == "SUCCESS") {
        coloredMessage = QString("<span style='color: #38A169;'>%1 [成功] %2</span>").arg(timestamp, message);
    } else {
        coloredMessage = QString("<span style='color: #4A5568;'>%1 [信息] %2</span>").arg(timestamp, message);
    }

    ui->logTextEdit->append(coloredMessage);

    // 自动滚动到底部
    if (ui->autoScrollCheckBox->isChecked()) {
        QScrollBar *scrollBar = ui->logTextEdit->verticalScrollBar();
        scrollBar->setValue(scrollBar->maximum());
    }

    logMessageCount++;
    updateLogCount();
}

void MainWindow::updateLogCount()
{
    ui->logCountLabel->setText(QString("条目: %1").arg(logMessageCount));
}

// ================== 视图控制 ==================

void MainWindow::setZoomFactor(double factor)
{
    currentZoomFactor = qMax(0.5, qMin(2.0, factor)); // 限制在50%-200%之间

    // 使用样式表实现缩放效果
    QString scaleStyle = QString("QWidget { font-size: %1pt; }")
                             .arg(qRound(9 * currentZoomFactor)); // 9pt是基础字体大小

    this->setStyleSheet(scaleStyle);

    // 更新状态栏显示当前缩放比例
    statusLabel->setText(QString("系统就绪 - 缩放: %1%").arg(qRound(currentZoomFactor * 100)));

    // 强制重新布局
    ui->centralwidget->update();
    this->update();
}

// ================== 态势评分计算 ==================

void MainWindow::updateSituationScores()
{
    // 同时更新红方和蓝方评分
    updateRedStatistics();
    updateBlueStatistics();
}

int MainWindow::calculateRedScore()
{
    const QList<Aircraft>& redAircrafts = redAircraftModel->getAircraftList();
    
    if (redAircrafts.isEmpty()) {
        return 0;
    }
    
    int totalScore = 0;
    
    for (const Aircraft& aircraft : redAircrafts) {
        int aircraftScore = 0;
        
        // 基础分数：每架飞机10分
        aircraftScore += 10;
        
        // 高度评分：高度越高分数越高 (0-20分)
        if (aircraft.altitude > 10000) {
            aircraftScore += 20;
        } else if (aircraft.altitude > 5000) {
            aircraftScore += 15;
        } else if (aircraft.altitude > 2000) {
            aircraftScore += 10;
        } else {
            aircraftScore += 5;
        }
        
        // 速度评分：速度越快分数越高 (0-15分)
        if (aircraft.speed > 800) {
            aircraftScore += 15;
        } else if (aircraft.speed > 600) {
            aircraftScore += 12;
        } else if (aircraft.speed > 400) {
            aircraftScore += 8;
        } else {
            aircraftScore += 5;
        }
        
        // 状态评分：不同状态有不同加分
        if (aircraft.status == "战斗") {
            aircraftScore += 15;
        } else if (aircraft.status == "巡航") {
            aircraftScore += 10;
        } else if (aircraft.status == "待命") {
            aircraftScore += 5;
        }
        
        totalScore += aircraftScore;
    }
    
    // 数量优势加成：飞机数量越多，额外加分
    int count = redAircrafts.size();
    if (count >= 10) {
        totalScore += count * 5;
    } else if (count >= 5) {
        totalScore += count * 3;
    } else if (count >= 3) {
        totalScore += count * 2;
    }
    
    return totalScore;
}

int MainWindow::calculateBlueScore()
{
    const QList<Aircraft>& blueAircrafts = blueAircraftModel->getAircraftList();
    
    if (blueAircrafts.isEmpty()) {
        return 0;
    }
    
    int totalScore = 0;
    
    for (const Aircraft& aircraft : blueAircrafts) {
        int aircraftScore = 0;
        
        // 基础分数：每架飞机10分
        aircraftScore += 10;
        
        // 高度评分：高度越高分数越高 (0-20分)
        if (aircraft.altitude > 10000) {
            aircraftScore += 20;
        } else if (aircraft.altitude > 5000) {
            aircraftScore += 15;
        } else if (aircraft.altitude > 2000) {
            aircraftScore += 10;
        } else {
            aircraftScore += 5;
        }
        
        // 速度评分：速度越快分数越高 (0-15分)
        if (aircraft.speed > 800) {
            aircraftScore += 15;
        } else if (aircraft.speed > 600) {
            aircraftScore += 12;
        } else if (aircraft.speed > 400) {
            aircraftScore += 8;
        } else {
            aircraftScore += 5;
        }
        
        // 状态评分：不同状态有不同加分
        if (aircraft.status == "战斗") {
            aircraftScore += 15;
        } else if (aircraft.status == "巡航") {
            aircraftScore += 10;
        } else if (aircraft.status == "待命") {
            aircraftScore += 5;
        }
        
        totalScore += aircraftScore;
    }
    
    // 数量优势加成：飞机数量越多，额外加分
    int count = blueAircrafts.size();
    if (count >= 10) {
        totalScore += count * 5;
    } else if (count >= 5) {
        totalScore += count * 3;
    } else if (count >= 3) {
        totalScore += count * 2;
    }
    
    return totalScore;
}

// ================== 推演控制函数 ==================

void MainWindow::on_pauseResumeButton_clicked()
{
    isPaused = !isPaused;
    
    if (isPaused) {
        ui->pauseResumeButton->setText("▶️ 继续");
        ui->pauseResumeButton->setStyleSheet(
            "QPushButton {"
            "    background-color: #38A169;"
            "    color: white;"
            "    border: none;"
            "    border-radius: 6px;"
            "    padding: 12px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #2F855A;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #276749;"
            "}"
        );
        addLogMessage("推演已暂停", "INFO");
    } else {
        ui->pauseResumeButton->setText("⏸️ 暂停");
        ui->pauseResumeButton->setStyleSheet(
            "QPushButton {"
            "    background-color: #ED8936;"
            "    color: white;"
            "    border: none;"
            "    border-radius: 6px;"
            "    padding: 12px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #DD6B20;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #C05621;"
            "}"
        );
        addLogMessage("推演已继续", "INFO");
    }
    
    // 更新控制文件（不显示重复日志）
    updateSimulationControlFile(false);
}

void MainWindow::on_blueModeComboBox_currentIndexChanged(int index)
{
    QString blueModeText;
    QString redModeText;
    int redModeIndex;
    
    switch (index) {
        case 0: // 蓝方攻击
            blueModeText = "攻击";
            redModeText = "防御";
            redModeIndex = 1;  // 红方自动变为防御
            break;
        case 1: // 蓝方防御
            blueModeText = "防御";
            redModeText = "攻击";
            redModeIndex = 0;  // 红方自动变为攻击
            break;
        case 2: // 蓝方对抗
            blueModeText = "对抗";
            redModeText = "对抗";
            redModeIndex = 2;  // 红方也是对抗
            break;
        default:
            blueModeText = "未知";
            redModeText = "未知";
            redModeIndex = index;
    }
    
    // 自动同步红方任务模式（对称设置，阻断信号避免循环触发）
    ui->redModeComboBox->blockSignals(true);
    ui->redModeComboBox->setCurrentIndex(redModeIndex);
    ui->redModeComboBox->blockSignals(false);
    
    // 记录模式变更
    addLogMessage(QString("任务模式已切换: 蓝方-%1 | 红方-%2").arg(blueModeText, redModeText), "INFO");
    
    // 更新控制文件（不显示重复日志）
    updateSimulationControlFile(false);
}

void MainWindow::on_redModeComboBox_currentIndexChanged(int index)
{
    QString redModeText;
    QString blueModeText;
    int blueModeIndex;
    
    switch (index) {
        case 0: // 红方攻击
            redModeText = "攻击";
            blueModeText = "防御";
            blueModeIndex = 1;  // 蓝方自动变为防御
            break;
        case 1: // 红方防御
            redModeText = "防御";
            blueModeText = "攻击";
            blueModeIndex = 0;  // 蓝方自动变为攻击
            break;
        case 2: // 红方对抗
            redModeText = "对抗";
            blueModeText = "对抗";
            blueModeIndex = 2;  // 蓝方也是对抗
            break;
        default:
            redModeText = "未知";
            blueModeText = "未知";
            blueModeIndex = index;
    }
    
    // 自动同步蓝方任务模式（对称设置，阻断信号避免循环触发）
    ui->blueModeComboBox->blockSignals(true);
    ui->blueModeComboBox->setCurrentIndex(blueModeIndex);
    ui->blueModeComboBox->blockSignals(false);
    
    // 记录模式变更
    addLogMessage(QString("任务模式已切换: 红方-%1 | 蓝方-%2").arg(redModeText, blueModeText), "INFO");
    
    // 更新控制文件（不显示重复日志）
    updateSimulationControlFile(false);
}

void MainWindow::on_speedComboBox_currentIndexChanged(int index)
{
    switch (index) {
        case 0: // 0.5x
            speedMultiplier = 0.5;
            break;
        case 1: // 1x
            speedMultiplier = 1.0;
            break;
        case 2: // 2x
            speedMultiplier = 2.0;
            break;
        case 3: // 5x
            speedMultiplier = 5.0;
            break;
        case 4: // 10x
            speedMultiplier = 10.0;
            break;
        default:
            speedMultiplier = 1.0;
    }
    
    addLogMessage(QString("推演倍速已设置为 %1x").arg(speedMultiplier), "INFO");
    
    // 更新控制文件（不显示重复日志）
    updateSimulationControlFile(false);
}

void MainWindow::updateSimulationControlFile(bool showLog)
{
    QJsonObject controlObj;
    controlObj["paused"] = isPaused;
    controlObj["speed_multiplier"] = speedMultiplier;  // 修改键名以匹配Python脚本
    controlObj["timestamp"] = QDateTime::currentDateTime().toString(Qt::ISODate);
    
    // 添加蓝方任务模式标识
    QString blueTaskMode;
    switch (ui->blueModeComboBox->currentIndex()) {
        case 0:
            blueTaskMode = "attack";
            break;
        case 1:
            blueTaskMode = "defense";
            break;
        case 2:
            blueTaskMode = "confrontation";
            break;
        default:
            blueTaskMode = "attack";  // 默认为攻击模式
    }
    controlObj["blue_task_mode"] = blueTaskMode;
    
    QJsonDocument doc(controlObj);
    
    QFile file(controlFilePath);
    if (file.open(QIODevice::WriteOnly)) {
        file.write(doc.toJson());
        file.close();
        
        // 根据参数决定是否添加日志信息
        if (showLog) {
            QString status = isPaused ? "暂停" : "运行";
            addLogMessage(QString("更新仿真控制: %1, 速度: %2x").arg(status).arg(speedMultiplier), "INFO");
        }
    } else {
        addLogMessage("无法写入仿真控制文件", "ERROR");
    }
}

void MainWindow::enableSimulationControls(bool enable)
{
    // 只控制暂停按钮，倍速框始终可用
    ui->pauseResumeButton->setEnabled(enable);
    
    if (!enable) {
        // 重置控制状态
        isPaused = false;
        ui->pauseResumeButton->setText("⏸️ 暂停");
        ui->pauseResumeButton->setStyleSheet(
            "QPushButton {"
            "    background-color: #ED8936;"
            "    color: white;"
            "    border: none;"
            "    border-radius: 6px;"
            "    padding: 12px;"
            "    font-weight: bold;"
            "    font-size: 13px;"
            "}"
            "QPushButton:hover {"
            "    background-color: #DD6B20;"
            "}"
            "QPushButton:pressed {"
            "    background-color: #C05621;"
            "}"
            "QPushButton:disabled {"
            "    background-color: #A0AEC0;"
            "    color: #718096;"
            "}"
        );
        // 重置状态后更新控制文件（不显示日志）
        updateSimulationControlFile(false);
    }
}

void MainWindow::on_onlineDebugButton_clicked()
{
    addLogMessage("启动在线调试功能...", "INFO");
    
    // 首先弹出文件选择对话框，选择想定XML文件
    QString fileName = QFileDialog::getOpenFileName(this,
                                                    "选择想定XML文件",
                                                    QDir::currentPath(),
                                                    "XML Files (*.xml)");
    
    if (fileName.isEmpty()) {
        addLogMessage("用户取消了文件选择", "INFO");
        return;
    }
    
    addLogMessage(QString("选择了想定文件: %1").arg(fileName), "INFO");
    
    // 从XML文件中加载红方态势
    QList<Aircraft> redAircraftList;
    if (!loadRedFromScenarioXml(fileName, redAircraftList)) {
        QMessageBox::critical(this, "错误", "无法解析想定XML文件或未找到红方态势数据");
        addLogMessage("想定XML文件解析失败", "ERROR");
        return;
    }
    
    // 清空当前红方数据并加载新数据
    redAircraftModel->clearAircraft();
    redAircraftModel->setAircraftList(redAircraftList);
    
    // 更新nextAircraftId
    int maxId = 0;
    for (const auto& aircraft : redAircraftList) {
        if (aircraft.id > maxId) maxId = aircraft.id;
    }
    nextAircraftId = maxId + 1;
    
    addLogMessage(QString("成功从想定文件加载%1架红方无人机").arg(redAircraftList.size()), "SUCCESS");
    QMessageBox::information(this, "成功", 
                             QString("已从想定文件加载%1架红方无人机\n正在启动在线调试...").arg(redAircraftList.size()));
    
    // 使用统一的项目根目录常量
    QString pythonScriptPath = PROJECT_ROOT_DIR + "online_debug.py";
    
    // 如果已有进程在运行，先终止
    if (pythonProcess) {
        pythonProcess->kill();
        pythonProcess->deleteLater();
        pythonProcess = nullptr;
        addLogMessage("已终止之前的调试进程", "INFO");
    }
    
    // 启动Python脚本
    pythonProcess = new QProcess(this);
    
    // 设置工作目录
    pythonProcess->setWorkingDirectory(PROJECT_ROOT_DIR);
    
    // 启动Python脚本
    QString pythonCommand = "python";
    QStringList arguments;
    arguments << "online_debug.py";
    
    // 连接信号槽以处理进程输出
    connect(pythonProcess, &QProcess::readyReadStandardOutput, [this]() {
        QByteArray data = pythonProcess->readAllStandardOutput();
        addLogMessage(QString("Python输出: %1").arg(QString::fromUtf8(data).trimmed()), "DEBUG");
    });
    
    connect(pythonProcess, &QProcess::readyReadStandardError, [this]() {
        QByteArray data = pythonProcess->readAllStandardError();
        addLogMessage(QString("Python错误: %1").arg(QString::fromUtf8(data).trimmed()), "ERROR");
    });
    
    connect(pythonProcess, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            [this](int exitCode, QProcess::ExitStatus exitStatus) {
        if (exitStatus == QProcess::CrashExit) {
            addLogMessage("Python调试脚本异常退出", "ERROR");
        } else {
            addLogMessage(QString("Python调试脚本正常退出，退出代码: %1").arg(exitCode), "INFO");
        }
        pythonProcess->deleteLater();
        pythonProcess = nullptr;
    });
    
    pythonProcess->start(pythonCommand, arguments);
    
    if (!pythonProcess->waitForStarted(3000)) {
        addLogMessage("启动Python调试脚本失败: " + pythonProcess->errorString(), "ERROR");
        pythonProcess->deleteLater();
        pythonProcess = nullptr;
    } else {
        addLogMessage("Python调试脚本启动成功", "INFO");
    }
}

void MainWindow::createPythonDebugScript(const QString &scriptPath)
{
    QFile file(scriptPath);
    if (file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        QTextStream out(&file);
        out.setCodec("UTF-8");
        
        // Write Python script content
        out << "#!/usr/bin/env python3\n";
        out << "# -*- coding: utf-8 -*-\n";
        out << "\"\"\"\n";
        out << "Online Debug Script\n";
        out << "Connect to remote server and receive red aircraft situation data\n";
        out << "\"\"\"\n\n";
        out << "import socket\n";
        out << "import threading\n";
        out << "import json\n";
        out << "import time\n";
        out << "import sys\n\n";
        
        out << "# Configuration parameters\n";
        out << "REMOTE_IP = '180.1.80.238'\n";
        out << "REMOTE_PORT = 1010\n";
        out << "LOCAL_IP = '180.1.80.129'\n";
        out << "LOCAL_PORT = 10113\n\n";
        
        out << "class OnlineDebugger:\n";
        out << "    def __init__(self):\n";
        out << "        self.running = True\n";
        out << "        self.remote_socket = None\n";
        out << "        self.local_socket = None\n\n";
        
        out << "    def connect_to_remote(self):\n";
        out << "        \"\"\"Connect to remote server\"\"\"\n";
        out << "        try:\n";
        out << "            self.remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n";
        out << "            self.remote_socket.connect((REMOTE_IP, REMOTE_PORT))\n";
        out << "            print(f'Successfully connected to remote server {REMOTE_IP}:{REMOTE_PORT}')\n";
        out << "            return True\n";
        out << "        except Exception as e:\n";
        out << "            print(f'Failed to connect to remote server: {e}')\n";
        out << "            return False\n\n";
        
        out << "    def start_local_server(self):\n";
        out << "        \"\"\"Start local server to receive red aircraft situation data\"\"\"\n";
        out << "        try:\n";
        out << "            self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n";
        out << "            self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n";
        out << "            self.local_socket.bind((LOCAL_IP, LOCAL_PORT))\n";
        out << "            self.local_socket.listen(5)\n";
        out << "            print(f'Local server started, listening on {LOCAL_IP}:{LOCAL_PORT}')\n";
        out << "            \n";
        out << "            while self.running:\n";
        out << "                try:\n";
        out << "                    client_socket, addr = self.local_socket.accept()\n";
        out << "                    print(f'Received connection from {addr}')\n";
        out << "                    \n";
        out << "                    # Create thread to handle client connection\n";
        out << "                    client_thread = threading.Thread(\n";
        out << "                        target=self.handle_client,\n";
        out << "                        args=(client_socket, addr)\n";
        out << "                    )\n";
        out << "                    client_thread.daemon = True\n";
        out << "                    client_thread.start()\n";
        out << "                    \n";
        out << "                except socket.error as e:\n";
        out << "                    if self.running:\n";
        out << "                        print(f'Error accepting connection: {e}')\n";
        out << "                        \n";
        out << "        except Exception as e:\n";
        out << "            print(f'Failed to start local server: {e}')\n\n";
        
        out << "    def handle_client(self, client_socket, addr):\n";
        out << "        \"\"\"Handle client connection\"\"\"\n";
        out << "        try:\n";
        out << "            while self.running:\n";
        out << "                data = client_socket.recv(4096)\n";
        out << "                if not data:\n";
        out << "                    break\n";
        out << "                    \n";
        out << "                # Parse received situation data\n";
        out << "                try:\n";
        out << "                    message = data.decode('utf-8')\n";
        out << "                    print(f'Received red aircraft situation data: {message}')\n";
        out << "                    \n";
        out << "                    # Try to parse JSON format situation data\n";
        out << "                    try:\n";
        out << "                        situation_data = json.loads(message)\n";
        out << "                        self.process_situation_data(situation_data)\n";
        out << "                    except json.JSONDecodeError:\n";
        out << "                        print('Received non-JSON format data, processing as text')\n";
        out << "                        \n";
        out << "                except UnicodeDecodeError:\n";
        out << "                    print('Received binary data')\n";
        out << "                    \n";
        out << "        except Exception as e:\n";
        out << "            print(f'Error handling client connection: {e}')\n";
        out << "        finally:\n";
        out << "            client_socket.close()\n";
        out << "            print(f'Connection with {addr} closed')\n\n";
        
        out << "    def process_situation_data(self, data):\n";
        out << "        \"\"\"Process situation data\"\"\"\n";
        out << "        print('Processing situation data:')\n";
        out << "        if isinstance(data, dict):\n";
        out << "            if 'red_aircraft' in data:\n";
        out << "                print(f'  Red aircraft count: {len(data[\"red_aircraft\"])}')\n";
        out << "                for aircraft in data['red_aircraft']:\n";
        out << "                    print(f'    Aircraft ID: {aircraft.get(\"id\", \"Unknown\")}, '\n";
        out << "                          f'Type: {aircraft.get(\"type\", \"Unknown\")}, '\n";
        out << "                          f'Position: ({aircraft.get(\"longitude\", 0)}, {aircraft.get(\"latitude\", 0)})')\n";
        out << "            \n";
        out << "            if 'timestamp' in data:\n";
        out << "                print(f'  Timestamp: {data[\"timestamp\"]}')\n";
        out << "        else:\n";
        out << "            print(f'  Data content: {data}')\n\n";
        
        out << "    def send_to_remote(self, data):\n";
        out << "        \"\"\"Send data to remote server\"\"\"\n";
        out << "        if self.remote_socket:\n";
        out << "            try:\n";
        out << "                if isinstance(data, dict):\n";
        out << "                    data = json.dumps(data, ensure_ascii=False)\n";
        out << "                self.remote_socket.send(data.encode('utf-8'))\n";
        out << "                print(f'Sent data to remote server: {data}')\n";
        out << "            except Exception as e:\n";
        out << "                print(f'Failed to send data to remote server: {e}')\n\n";
        
        out << "    def run(self):\n";
        out << "        \"\"\"Run debugger\"\"\"\n";
        out << "        print('Starting online debugger...')\n";
        out << "        \n";
        out << "        # Connect to remote server\n";
        out << "        if self.connect_to_remote():\n";
        out << "            # Start local server thread\n";
        out << "            server_thread = threading.Thread(target=self.start_local_server)\n";
        out << "            server_thread.daemon = True\n";
        out << "            server_thread.start()\n";
        out << "            \n";
        out << "            try:\n";
        out << "                print('Debugger running, press Ctrl+C to exit...')\n";
        out << "                while self.running:\n";
        out << "                    time.sleep(1)\n";
        out << "            except KeyboardInterrupt:\n";
        out << "                print('\\nReceived exit signal')\n";
        out << "        \n";
        out << "        self.cleanup()\n\n";
        
        out << "    def cleanup(self):\n";
        out << "        \"\"\"Clean up resources\"\"\"\n";
        out << "        print('Cleaning up resources...')\n";
        out << "        self.running = False\n";
        out << "        \n";
        out << "        if self.remote_socket:\n";
        out << "            self.remote_socket.close()\n";
        out << "            print('Remote connection closed')\n";
        out << "            \n";
        out << "        if self.local_socket:\n";
        out << "            self.local_socket.close()\n";
        out << "            print('Local server closed')\n\n";
        
        out << "if __name__ == '__main__':\n";
        out << "    debugger = OnlineDebugger()\n";
        out << "    try:\n";
        out << "        debugger.run()\n";
        out << "    except Exception as e:\n";
        out << "        print(f'Program exited with exception: {e}')\n";
        out << "        debugger.cleanup()\n";
        
        file.close();
        addLogMessage("Python debug script created successfully: " + scriptPath, "INFO");
    } else {
        addLogMessage("Failed to create Python debug script: " + file.errorString(), "ERROR");
    }
}

void MainWindow::on_killAllProcessesButton_clicked()
{
    addLogMessage("正在杀死所有进程...", "WARNING");
    
    int killedCount = 0;
    
    // 杀死Python进程
    if (pythonProcess) {
        if (pythonProcess->state() != QProcess::NotRunning) {
            pythonProcess->kill();
            pythonProcess->waitForFinished(1000);
            addLogMessage("已杀死Python调试进程", "INFO");
            killedCount++;
        }
        pythonProcess->deleteLater();
        pythonProcess = nullptr;
    }
    
    // 检查是否有其他Python进程需要杀死
    QProcess process;
    process.start("tasklist", QStringList() << "/FI" << "IMAGENAME eq python.exe" << "/FO" << "CSV");
    process.waitForFinished(2000);
    
    if (process.exitCode() == 0) {
        QByteArray output = process.readAllStandardOutput();
        QStringList lines = QString::fromUtf8(output).split("\n", QString::SkipEmptyParts);
        
        // 跳过标题行
        for (int i = 1; i < lines.size(); i++) {
            QString line = lines[i];
            if (line.contains("python.exe")) {
                QStringList parts = line.split(",");
                if (parts.size() >= 2) {
                    QString pidStr = parts[1].trimmed().replace("\"", "");
                    bool ok;
                    int pid = pidStr.toInt(&ok);
                    if (ok) {
                        QProcess::execute("taskkill", QStringList() << "/PID" << QString::number(pid) << "/F");
                        addLogMessage(QString("已杀死Python进程 (PID: %1)").arg(pid), "INFO");
                        killedCount++;
                    }
                }
            }
        }
    }
    
    // 检查是否有online_debug.py进程
    process.start("tasklist", QStringList() << "/FI" << "IMAGENAME eq python.exe" << "/FO" << "CSV");
    process.waitForFinished(2000);
    
    if (process.exitCode() == 0) {
        QByteArray output = process.readAllStandardOutput();
        if (output.contains("online_debug")) {
            QProcess::execute("taskkill", QStringList() << "/IM" << "python.exe" << "/FI" << "WINDOWTITLE eq online_debug*" << "/F");
            addLogMessage("已杀死所有online_debug相关进程", "INFO");
            killedCount++;
        }
    }
    
    if (killedCount > 0) {
        addLogMessage(QString("成功杀死 %1 个进程").arg(killedCount), "SUCCESS");
    } else {
        addLogMessage("没有找到需要杀死的进程", "INFO");
    }
}
// ================== 事件过滤器 ==================

bool MainWindow::eventFilter(QObject *obj, QEvent *event)
{
    // 处理表格视图的鼠标点击事件
    if (event->type() == QEvent::MouseButtonPress) {
        QMouseEvent *mouseEvent = static_cast<QMouseEvent*>(event);
        
        // 检查是否是红方或蓝方表格的viewport
        if (obj == ui->redTableView->viewport() || obj == ui->blueTableView->viewport()) {
            QTableView *tableView = (obj == ui->redTableView->viewport()) ? ui->redTableView : ui->blueTableView;
            
            // 获取点击位置对应的索引
            QModelIndex index = tableView->indexAt(mouseEvent->pos());
            
            // 如果点击的是空白区域（无效索引），清除选择
            if (!index.isValid()) {
                tableView->clearSelection();
                return true; // 事件已处理
            }
        }
    }
    
    // 继续传递事件
    return QMainWindow::eventFilter(obj, event);
}

// ================== XML文件处理函数 ==================

bool MainWindow::saveToXml(const QString &fileName, const QList<Aircraft> &redList, 
                           const QList<Aircraft> &blueList, const QJsonObject &params)
{
    QFile file(fileName);
    if (!file.open(QIODevice::WriteOnly)) {
        return false;
    }

    QXmlStreamWriter writer(&file);
    writer.setAutoFormatting(true);
    writer.writeStartDocument();
    
    writer.writeStartElement("situation");
    
    // 写入红方飞机
    writer.writeStartElement("red_aircraft");
    for (const auto& aircraft : redList) {
        writer.writeStartElement("aircraft");
        writer.writeTextElement("id", QString::number(aircraft.id));
        writer.writeTextElement("type", aircraft.type);
        writer.writeTextElement("longitude", QString::number(aircraft.longitude));
        writer.writeTextElement("latitude", QString::number(aircraft.latitude));
        writer.writeTextElement("altitude", QString::number(aircraft.altitude));
        writer.writeTextElement("speed", QString::number(aircraft.speed));
        writer.writeTextElement("heading", QString::number(aircraft.heading));
        writer.writeTextElement("status", aircraft.status);
        writer.writeEndElement(); // aircraft
    }
    writer.writeEndElement(); // red_aircraft
    
    // 写入蓝方飞机
    writer.writeStartElement("blue_aircraft");
    for (const auto& aircraft : blueList) {
        writer.writeStartElement("aircraft");
        writer.writeTextElement("id", QString::number(aircraft.id));
        writer.writeTextElement("type", aircraft.type);
        writer.writeTextElement("longitude", QString::number(aircraft.longitude));
        writer.writeTextElement("latitude", QString::number(aircraft.latitude));
        writer.writeTextElement("altitude", QString::number(aircraft.altitude));
        writer.writeTextElement("speed", QString::number(aircraft.speed));
        writer.writeTextElement("heading", QString::number(aircraft.heading));
        writer.writeTextElement("status", aircraft.status);
        writer.writeEndElement(); // aircraft
    }
    writer.writeEndElement(); // blue_aircraft
    
    // 写入参数
    writer.writeStartElement("parameters");
    writer.writeTextElement("blue_count", QString::number(params["blue_count"].toInt()));
    writer.writeTextElement("strategy", params["strategy"].toString());
    if (params.contains("task_mode")) {
        writer.writeTextElement("task_mode", params["task_mode"].toString());
    }
    writer.writeEndElement(); // parameters
    
    writer.writeEndElement(); // situation
    writer.writeEndDocument();
    
    file.close();
    return true;
}

bool MainWindow::loadFromXml(const QString &fileName, QList<Aircraft> &aircraftList, QJsonObject &params)
{
    QFile file(fileName);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }

    QXmlStreamReader reader(&file);
    aircraftList.clear();
    
    Aircraft currentAircraft;
    QString currentElement;
    bool inRedAircraft = false;
    bool inParameters = false;
    
    while (!reader.atEnd()) {
        reader.readNext();
        
        if (reader.isStartElement()) {
            currentElement = reader.name().toString();
            
            if (currentElement == "red_aircraft") {
                inRedAircraft = true;
            } else if (currentElement == "parameters") {
                inParameters = true;
            } else if (currentElement == "aircraft" && inRedAircraft) {
                currentAircraft = Aircraft();
            }
        } else if (reader.isEndElement()) {
            QString endElement = reader.name().toString();
            
            if (endElement == "red_aircraft") {
                inRedAircraft = false;
            } else if (endElement == "parameters") {
                inParameters = false;
            } else if (endElement == "aircraft" && inRedAircraft) {
                aircraftList.append(currentAircraft);
            }
        } else if (reader.isCharacters() && !reader.isWhitespace()) {
            QString text = reader.text().toString();
            
            if (inRedAircraft) {
                if (currentElement == "id") currentAircraft.id = text.toInt();
                else if (currentElement == "type") currentAircraft.type = text;
                else if (currentElement == "longitude") currentAircraft.longitude = text.toDouble();
                else if (currentElement == "latitude") currentAircraft.latitude = text.toDouble();
                else if (currentElement == "altitude") currentAircraft.altitude = text.toDouble();
                else if (currentElement == "speed") currentAircraft.speed = text.toDouble();
                else if (currentElement == "heading") currentAircraft.heading = text.toDouble();
                else if (currentElement == "status") currentAircraft.status = text;
            } else if (inParameters) {
                if (currentElement == "blue_count") params["blue_count"] = text.toInt();
                else if (currentElement == "strategy") params["strategy"] = text;
                else if (currentElement == "task_mode") params["task_mode"] = text;
            }
        }
    }
    
    file.close();
    
    if (reader.hasError()) {
        return false;
    }
    
    return true;
}

bool MainWindow::loadRedFromScenarioXml(const QString &fileName, QList<Aircraft> &aircraftList)
{
    QFile file(fileName);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }

    QXmlStreamReader reader(&file);
    aircraftList.clear();
    
    // 用于跟踪当前解析状态
    bool inRedSide = false;         // 是否在<红方>标签内
    bool inAirDomain = false;       // 是否在<空中>标签内
    bool inEntity = false;          // 是否在<实体>标签内
    
    // 临时存储当前实体信息
    QString currentEntityId;
    QString currentEntityName;
    QString currentEntityModel;
    QString currentEntityPosition;
    QString currentElement;
    
    int aircraftIndex = 1;  // 用于生成飞机ID
    
    while (!reader.atEnd()) {
        reader.readNext();
        
        if (reader.isStartElement()) {
            currentElement = reader.name().toString();
            
            // 检测<红方>标签
            if (currentElement == "红方" || currentElement == QString::fromUtf8("红方")) {
                inRedSide = true;
                addLogMessage("开始解析红方数据", "INFO");
            }
            // 检测<空中>标签
            else if ((currentElement == "空中" || currentElement == QString::fromUtf8("空中")) && inRedSide) {
                inAirDomain = true;
                addLogMessage("开始解析空中实体", "INFO");
            }
            // 检测<实体>标签
            else if ((currentElement == "实体" || currentElement == QString::fromUtf8("实体")) && inRedSide && inAirDomain) {
                inEntity = true;
                // 获取实体ID属性
                currentEntityId = reader.attributes().value("ID").toString();
                // 重置其他字段
                currentEntityName = "";
                currentEntityModel = "";
                currentEntityPosition = "";
            }
            
        } else if (reader.isEndElement()) {
            QString endElement = reader.name().toString();
            
            // 结束<红方>标签
            if (endElement == "红方" || endElement == QString::fromUtf8("红方")) {
                inRedSide = false;
            }
            // 结束<空中>标签
            else if (endElement == "空中" || endElement == QString::fromUtf8("空中")) {
                inAirDomain = false;
            }
            // 结束<实体>标签 - 保存当前实体
            else if ((endElement == "实体" || endElement == QString::fromUtf8("实体")) && inEntity) {
                inEntity = false;
                
                // 解析位置字符串（格式：经度,纬度,高度）
                if (!currentEntityPosition.isEmpty()) {
                    QStringList posParts = currentEntityPosition.split(',');
                    if (posParts.size() >= 3) {
                        double longitude = posParts[0].toDouble();
                        double latitude = posParts[1].toDouble();
                        double altitude = posParts[2].toDouble();
                        
                        // 创建Aircraft对象
                        Aircraft aircraft;
                        aircraft.id = aircraftIndex++;
                        aircraft.type = currentEntityName.isEmpty() ? "无人机" : currentEntityName;
                        aircraft.longitude = longitude;
                        aircraft.latitude = latitude;
                        aircraft.altitude = altitude;
                        aircraft.speed = 200.0;  // 默认速度
                        aircraft.heading = 0.0;  // 默认航向
                        aircraft.status = "待命"; // 默认状态
                        
                        aircraftList.append(aircraft);
                        
                        addLogMessage(QString("解析实体: ID=%1, 名称=%2, 位置=(%3, %4, %5)")
                                          .arg(currentEntityId)
                                          .arg(currentEntityName)
                                          .arg(longitude, 0, 'f', 6)
                                          .arg(latitude, 0, 'f', 6)
                                          .arg(altitude, 0, 'f', 2), "DEBUG");
                    }
                }
            }
            
        } else if (reader.isCharacters() && !reader.isWhitespace()) {
            QString text = reader.text().toString().trimmed();
            
            if (inEntity && inRedSide && inAirDomain) {
                // 提取实体名称
                if (currentElement == "名称" || currentElement == QString::fromUtf8("名称")) {
                    currentEntityName = text;
                }
                // 提取实体型号
                else if (currentElement == "型号" || currentElement == QString::fromUtf8("型号")) {
                    currentEntityModel = text;
                }
                // 提取实体位置
                else if (currentElement == "位置" || currentElement == QString::fromUtf8("位置")) {
                    currentEntityPosition = text;
                }
            }
        }
    }
    
    file.close();
    
    if (reader.hasError()) {
        addLogMessage(QString("XML解析错误: %1").arg(reader.errorString()), "ERROR");
        return false;
    }
    
    addLogMessage(QString("成功解析%1架红方无人机").arg(aircraftList.size()), "SUCCESS");
    return !aircraftList.isEmpty();
}
