"""统一日志模块 - 支持文件+控制台双输出

用法:
    from photogram_toolbox.core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("消息")
    logger.debug("详细调试信息")
    logger.timing_start("步骤名")
    logger.timing_end("步骤名")
"""
import os
import time
import logging
from datetime import datetime
from pathlib import Path


class TimingLogger:
    """带耗时统计的日志器"""

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._timers: dict = {}

    def _log(self, level: int, msg: str, **kwargs):
        """统一日志方法,附带额外字段"""
        extra = ""
        if kwargs:
            parts = [f"{k}={v}" for k, v in kwargs.items()]
            extra = " | " + " ".join(parts)
        self._logger.log(level, f"{msg}{extra}")

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, exc_info=True, **kwargs)

    def timing_start(self, name: str):
        """开始计时"""
        self._timers[name] = time.perf_counter()
        self._logger.debug(f"[TIMING] 开始: {name}")

    def timing_end(self, name: str):
        """结束计时并记录耗时"""
        if name not in self._timers:
            self._logger.warning(f"[TIMING] 未找到计时器: {name}")
            return
        elapsed = time.perf_counter() - self._timers.pop(name)
        self._logger.info(f"[TIMING] {name} 耗时: {elapsed:.3f}s")
        return elapsed

    def step(self, step_name: str, current: int, total: int):
        """记录步骤进度"""
        self._logger.info(f"[STEP] ({current}/{total}) {step_name}")


# 全局日志器缓存
_loggers: dict = {}
_log_dir: str = ""


def setup_logging(log_dir: str = "", level: int = logging.DEBUG,
                  console_level: int = logging.INFO):
    """配置全局日志

    Args:
        log_dir: 日志文件目录(空则不写文件)
        level: 文件日志级别
        console_level: 控制台日志级别
    """
    global _log_dir
    _log_dir = log_dir

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    # 配置根日志器
    root = logging.getLogger("photogram_toolbox")
    root.setLevel(level)
    root.handlers.clear()

    # 控制台输出
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(console)

    # 文件输出
    if log_dir:
        log_file = os.path.join(
            log_dir,
            f"photogram_toolbox_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-5s] %(name)s:%(lineno)d: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        root.addHandler(file_handler)

    root.info(f"日志系统初始化, log_dir={log_dir or 'console only'}")


def get_logger(name: str) -> TimingLogger:
    """获取日志器

    Args:
        name: 通常用 __name__

    Returns:
        TimingLogger 实例
    """
    if name not in _loggers:
        # 确保 name 以 photogram_toolbox 开头
        if not name.startswith("photogram_toolbox"):
            name = f"photogram_toolbox.{name}"
        logger = logging.getLogger(name)
        _loggers[name] = TimingLogger(logger)
    return _loggers[name]
