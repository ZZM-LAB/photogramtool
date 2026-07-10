"""进度反馈接口 - 算法与 GUI 之间的通信桥梁"""


class AlgoFeedback:
    """算法执行进度反馈

    GUI 层继承此类并重写方法，将进度/日志路由到界面控件。
    算法层通过 feedback 报告进度，不直接操作 UI。
    """

    def __init__(self):
        self._canceled = False

    def set_progress(self, percent: int) -> None:
        """设置进度 0-100"""
        pass

    def set_progress_text(self, text: str) -> None:
        """设置当前阶段描述"""
        pass

    def push_info(self, msg: str) -> None:
        """普通信息"""
        print(f"[INFO] {msg}")

    def push_warning(self, msg: str) -> None:
        """警告"""
        print(f"[WARN] {msg}")

    def report_error(self, msg: str, fatal: bool = False) -> None:
        """错误"""
        print(f"[ERROR] {msg}")

    def is_canceled(self) -> bool:
        """是否被用户取消"""
        return self._canceled

    def cancel(self) -> None:
        """请求取消"""
        self._canceled = True
