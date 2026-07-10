"""photogram_toolbox.algorithms - 38个摄影测量算法

导入此包会自动注册所有已实现的算法到 REGISTRY。

模块:
    m1_aerial_triangulation  - 空中三角测量 (A01-A06)
    m2_dem                   - DEM生产 (A07-A13)
    m3_dom                   - DOM生产 (A14-A18)
    m4_dlg                   - DLG提取 (A19-A24)
    m5_flight_planning       - 航线规划 (A25-A28)
    m6_quality               - 质量评定 (A29-A33)
    m7_3d_modeling           - 三维建模 (A34-A38)
"""
# 导入各模块，触发算法注册
from . import m1_aerial_triangulation
from . import m2_dem
from . import m3_dom
from . import m4_dlg
from . import m5_flight_planning
from . import m6_quality
from . import m7_3d_modeling

__all__ = [
    "m1_aerial_triangulation", "m2_dem", "m3_dom", "m4_dlg",
    "m5_flight_planning", "m6_quality", "m7_3d_modeling",
]
