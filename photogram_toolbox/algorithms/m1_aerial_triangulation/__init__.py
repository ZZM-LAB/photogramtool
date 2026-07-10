"""M1 空中三角测量模块 (A01-A06)

算法列表:
    A01 影像自动内定向          - 导入影像,推断相机内方位元素
    A02 SIFT特征提取与匹配      - 提取SIFT特征,全量匹配
    A03 逐步增量SfM重建         - 增量式运动恢复结构
    A04 控制点识别与配准        - 对齐到大地坐标系
    A05 全局Bundle Adjustment   - 光束平差精修
    A06 立体模型生成            - 影像去畸变,为MVS做准备
"""
from .a01_interior_orientation import A01InteriorOrientation
from .a02_feature_matching import A02FeatureExtractionMatching
from .a03_incremental_sfm import A03IncrementalSfM
from .a04_control_point_registration import A04ControlPointRegistration
from .a05_bundle_adjustment import A05GlobalBundleAdjustment
from .a06_stereo_model import A06StereoModelGeneration

__all__ = [
    "A01InteriorOrientation",
    "A02FeatureExtractionMatching",
    "A03IncrementalSfM",
    "A04ControlPointRegistration",
    "A05GlobalBundleAdjustment",
    "A06StereoModelGeneration",
]
