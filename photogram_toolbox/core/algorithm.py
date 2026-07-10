"""算法基类 - 所有 38 个算法的统一接口

参考 QGIS Processing Framework 设计：
- 算法是无状态对象，每次执行独立
- process() 是核心方法，接收输入/上下文/反馈，返回结果
- 算法通过 REGISTRY 注册，供 GUI/CLI 发现和调用
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from .context import AlgoContext
from .feedback import AlgoFeedback
from .sink import AlgoSink


@dataclass
class AlgoResult:
    """算法执行结果"""
    status: int = 0          # 0=成功, 非0=错误码
    message: str = ""        # 状态描述
    outputs: list = field(default_factory=list)  # 产物文件路径列表
    metadata: dict = field(default_factory=dict)  # 附加信息（统计/报告等）

    @property
    def success(self) -> bool:
        return self.status == 0


# 状态码常量
STATUS_OK = 0
STATUS_ERROR = 1
STATUS_CANCELED = 2


class Algorithm(ABC):
    """算法抽象基类

    子类必须实现:
        name()        - 算法唯一标识 (如 "a01_interior_orientation")
        display_name() - 显示名称
        group()       - 模块分组 (如 "M1 空中三角测量")
        process()     - 核心执行逻辑
    """

    @staticmethod
    @abstractmethod
    def name() -> str:
        """算法唯一标识符"""
        ...

    @staticmethod
    @abstractmethod
    def display_name() -> str:
        """用户可见名称"""
        ...

    @staticmethod
    @abstractmethod
    def group() -> str:
        """所属模块"""
        ...

    @staticmethod
    def group_id() -> str:
        """模块 ID（用于分组）"""
        return ""

    @staticmethod
    def short_help() -> str:
        """简短帮助文本"""
        return ""

    @staticmethod
    def can_execute() -> bool:
        """是否可执行（检查依赖是否满足）"""
        return True

    @abstractmethod
    def process(self, input_data: Any, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """执行算法

        Args:
            input_data: 输入数据（路径/数组/对象，由算法类型决定）
            context: 运行上下文
            feedback: 进度反馈

        Returns:
            AlgoResult
        """
        ...
