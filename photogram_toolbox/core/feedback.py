"""进度反馈接口 - 算法与 GUI 之间的通信桥梁

集成了统一日志器,所有 push_info/warning/error 自动写入日志文件。
"""

from .logger import get_logger


class AlgoFeedback:
    """算法执行进度反馈

    GUI 层继承此类并重写方法，将进度/日志路由到界面控件。
    算法层通过 feedback 报告进度，不直接操作 UI。

    所有日志方法同时输出到日志文件(通过 logger)。
    """

    def __init__(self):
        self._canceled = False
        self._logger = get_logger("feedback")

    def set_progress(self, percent: int) -> None:
        """设置进度 0-100"""
        self._logger.debug(f"进度: {percent}%")

    def set_progress_text(self, text: str) -> None:
        """设置当前阶段描述"""
        self._logger.info(f"阶段: {text}")

    def push_info(self, msg: str) -> None:
        """普通信息"""
        self._logger.info(msg)
        print(f"[INFO] {msg}")

    def push_warning(self, msg: str) -> None:
        """警告"""
        self._logger.warning(msg)
        print(f"[WARN] {msg}")

    def report_error(self, msg: str, fatal: bool = False) -> None:
        """错误"""
        level = "FATAL" if fatal else "ERROR"
        self._logger.error(f"[{level}] {msg}")
        print(f"[{level}] {msg}")

    def is_canceled(self) -> bool:
        """是否被用户取消"""
        return self._canceled

    def cancel(self) -> None:
        """请求取消"""
        self._canceled = True
        self._logger.warning("用户请求取消")
