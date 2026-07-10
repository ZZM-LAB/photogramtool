"""photogram_toolbox 启动入口

用法:
    python -m photogram_toolbox.main        # 启动 GUI
    python -m photogram_toolbox.main --list  # 列出所有算法
"""
import sys


def list_algorithms():
    """列出所有已注册算法"""
    from photogram_toolbox.core import REGISTRY
    import photogram_toolbox.algorithms  # 触发注册

    print(f"已注册算法: {REGISTRY.count()} 个\n")
    groups = {}
    for algo_cls in REGISTRY.algorithms():
        gid = algo_cls.group_id() or "other"
        groups.setdefault(gid, []).append(algo_cls)

    for gid in sorted(groups.keys()):
        algos = groups[gid]
        gname = algos[0].group()
        print(f"=== {gname} ({gid}) ===")
        for algo_cls in sorted(algos, key=lambda a: a.name()):
            can = "OK" if algo_cls.can_execute() else "MISSING"
            print(f"  [{can}] {algo_cls.name():<35} {algo_cls.display_name()}")
        print()


def launch_gui():
    """启动 GUI"""
    from PyQt5.QtWidgets import QApplication
    from photogram_toolbox.gui import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


def main():
    if "--list" in sys.argv:
        list_algorithms()
    else:
        launch_gui()


if __name__ == "__main__":
    main()
