"""M2 DEM自动生产模块 (A07-A13)

算法列表:
    A07 MVS多视角密集匹配      - COLMAP patch_match_stereo
    A08 点云自动去噪           - Open3D 统计离群点去除
    A09 地面点自动滤波         - Open3D RANSAC平面分割
    A10 IDW插值生成DEM         - scipy cKDTree + rasterio
    A11 DEM平滑与孔洞填充      - scipy.ndimage 中值滤波
    A12 DEM精度自动评定        - 与参考高程点对比
    A13 DEM等高线自动生成      - matplotlib.contour
"""
from .a07_mvs_dense_matching import A07MVSDenseMatching
from .a08_pointcloud_denoising import A08PointcloudDenoising
from .a09_ground_filtering import A09GroundFiltering
from .a10_idw_dem import A10IDWInterpolationDEM
from .a11_dem_smoothing import A11DEMSmoothing
from .a12_dem_accuracy import A12DEMAccuracyAssessment
from .a13_contour_generation import A13ContourGeneration

__all__ = [
    "A07MVSDenseMatching",
    "A08PointcloudDenoising",
    "A09GroundFiltering",
    "A10IDWInterpolationDEM",
    "A11DEMSmoothing",
    "A12DEMAccuracyAssessment",
    "A13ContourGeneration",
]
