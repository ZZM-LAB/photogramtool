"""photogram_toolbox - 摄影测量全流程自动化算法工具箱

38 个算法覆盖摄影测量完整流程:
    M1 空中三角测量 (A01-A06)
    M2 DEM生产      (A07-A13)
    M3 DOM生产      (A14-A18)
    M4 DLG提取      (A19-A24)
    M5 航线规划     (A25-A28)
    M6 质量评定     (A29-A33)
    M7 三维建模     (A34-A38)

快速开始:
    from photogram_toolbox.core import REGISTRY
    import photogram_toolbox.algorithms  # 触发注册

    print(f"已注册算法: {REGISTRY.count()} 个")
    for algo in REGISTRY.algorithms():
        print(f"  {algo.name():<35} {algo.display_name()}")
"""
from .core import (
    Algorithm, AlgoResult, AlgoContext, AlgoFeedback,
    AlgoSink, FileSink, MemorySink,
    REGISTRY, Pipeline, PipelineStep,
)

__version__ = "0.1.0"
