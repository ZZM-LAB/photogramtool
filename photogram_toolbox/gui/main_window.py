"""主窗口 - 摄影测量工具箱 GUI

骨架版本:
    - 左侧: 算法树（按 M1-M7 分组）
    - 右侧: 参数面板 + 进度区
    - 底部: 状态栏

后续逐步扩展: 影像显示 Canvas / 点云预览 / 结果对比
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QPushButton, QStatusBar, QSplitter, QHeaderView
)
from PyQt5.QtCore import Qt
from photogram_toolbox.core import REGISTRY


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("摄影测量工具箱 Photogram Toolbox")
        self.resize(1200, 800)

        # 触发算法注册
        import photogram_toolbox.algorithms  # noqa: F401

        self._init_ui()
        self._load_algorithms()

    def _init_ui(self):
        """构建界面"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # 左侧: 算法树
        self.algo_tree = QTreeWidget()
        self.algo_tree.setHeaderLabels(["算法", "ID"])
        self.algo_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.algo_tree.setColumnWidth(1, 200)
        splitter.addWidget(self.algo_tree)

        # 右侧: 参数面板 + 日志
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.param_label = QLabel("请选择左侧算法查看参数")
        right_layout.addWidget(self.param_label)

        self.run_btn = QPushButton("运行")
        self.run_btn.setEnabled(False)
        right_layout.addWidget(self.run_btn)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("运行日志将显示在这里...")
        right_layout.addWidget(self.log_view, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([400, 800])

        # 状态栏
        self.statusBar().showMessage(
            f"已加载 {REGISTRY.count()} 个算法 | gisenv 环境"
        )

        # 信号
        self.algo_tree.itemClicked.connect(self._on_algo_selected)
        self.run_btn.clicked.connect(self._on_run)

    def _load_algorithms(self):
        """将已注册算法填充到树"""
        # 按 group_id 分组
        groups = {}
        for algo_cls in REGISTRY.algorithms():
            gid = algo_cls.group_id() or "other"
            gname = algo_cls.group()
            if gid not in groups:
                groups[gid] = (gname, [])
            groups[gid][1].append(algo_cls)

        # 排序: m1-m7
        for gid in sorted(groups.keys()):
            gname, algos = groups[gid]
            gitem = QTreeWidgetItem([gname, gid])
            self.algo_tree.addTopLevelItem(gitem)
            for algo_cls in sorted(algos, key=lambda a: a.name()):
                item = QTreeWidgetItem([algo_cls.display_name(), algo_cls.name()])
                gitem.addChild(item)
            gitem.setExpanded(True)

    def _on_algo_selected(self, item, column):
        """选中算法时显示帮助"""
        algo_id = item.text(1)
        algo_cls = REGISTRY.algorithm_by_id(algo_id)
        if algo_cls:
            help_text = algo_cls.short_help() or "(无帮助)"
            can_run = algo_cls.can_execute()
            status = "可执行" if can_run else "依赖缺失"
            self.param_label.setText(
                f"{algo_cls.display_name()}\n{algo_id}\n\n{help_text}\n\n状态: {status}"
            )
            self.run_btn.setEnabled(can_run)
        else:
            self.param_label.setText("请选择具体算法（非分组节点）")
            self.run_btn.setEnabled(False)

    def _on_run(self):
        """运行选中算法（骨架: 仅打印日志）"""
        item = self.algo_tree.currentItem()
        if not item:
            return
        algo_id = item.text(1)
        self.log_view.append(f"[待实现] 运行算法: {algo_id}")
        self.log_view.append("  -> 参数对话框 / 输入选择 / 线程执行 待后续实现")
