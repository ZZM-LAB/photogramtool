"""photogram_toolbox.core - 核心框架

导出:
    Algorithm, AlgoResult      - 算法基类与结果
    AlgoContext, AlgoFeedback  - 上下文与反馈
    AlgoSink, FileSink         - 输出 sink
    REGISTRY                   - 算法注册表
    Pipeline                   - 流水线编排
"""
from .algorithm import Algorithm, AlgoResult, STATUS_OK, STATUS_ERROR, STATUS_CANCELED
from .context import AlgoContext
from .feedback import AlgoFeedback
from .sink import AlgoSink, FileSink, MemorySink
from .registry import REGISTRY, AlgorithmRegistry
from .pipeline import Pipeline, PipelineStep

__all__ = [
    "Algorithm", "AlgoResult", "STATUS_OK", "STATUS_ERROR", "STATUS_CANCELED",
    "AlgoContext", "AlgoFeedback",
    "AlgoSink", "FileSink", "MemorySink",
    "REGISTRY", "AlgorithmRegistry",
    "Pipeline", "PipelineStep",
]
