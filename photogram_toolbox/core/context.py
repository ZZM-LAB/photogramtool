"""算法运行上下文 - 承载输入输出路径、参数、CRS 等运行时信息"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AlgoContext:
    """算法执行上下文（不可变数据类）

    算法通过 context 获取运行时环境信息，不直接访问全局状态。
    """
    # 工作目录（中间产物存放）
    work_dir: str = ""
    # 输出目录（最终产物）
    output_dir: str = ""
    # 坐标参考系 WKT
    crs_wkt: str = ""
    # 影像范围 [xmin, ymin, xmax, ymax]
    extent: tuple = (0.0, 0.0, 0.0, 0.0)
    # 像素分辨率 [xres, yres]
    pixel_size: tuple = (1.0, 1.0)
    # 算法参数（动态键值对）
    parameters: dict = field(default_factory=dict)
    # 是否取消（由 feedback 管理，这里仅作快照）
    canceled: bool = False

    def param(self, key: str, default: Any = None) -> Any:
        """便捷取参"""
        return self.parameters.get(key, default)
