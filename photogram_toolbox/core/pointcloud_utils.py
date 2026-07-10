"""Open3D 点云工具 - 点云读写/去噪/滤波/网格操作

封装 Open3D 常用操作,供 A08-A13 调用。
"""
import os
import numpy as np


def load_pointcloud(ply_path: str):
    """加载点云"""
    import open3d as o3d
    pcd = o3d.io.read_point_cloud(ply_path)
    if not pcd.has_points():
        raise ValueError(f"点云为空或读取失败: {ply_path}")
    return pcd


def save_pointcloud(pcd, ply_path: str):
    """保存点云"""
    import open3d as o3d
    os.makedirs(os.path.dirname(ply_path), exist_ok=True)
    o3d.io.write_point_cloud(ply_path, pcd)


def statistical_outlier_removal(pcd, nb_neighbors: int = 20,
                                std_ratio: float = 2.0):
    """统计离群点去除

    Args:
        pcd: open3d 点云
        nb_neighbors: 邻域点数
        std_ratio: 标准差倍数

    Returns:
        (cleaned_pcd, removed_pcd)
    """
    cleaned, ind = pcd.remove_statistical_outlier(
        nb_neighbors=nb_neighbors, std_ratio=std_ratio
    )
    removed = pcd.select_by_index(ind, invert=True)
    return cleaned, removed


def segment_ground_ransac(pcd, distance_threshold: float = 0.3,
                          ransac_n: int = 3,
                          num_iterations: int = 1000):
    """RANSAC 平面分割分离地面点

    假设地面是最大平面,用 RANSAC 拟合平面方程 ax+by+cz+d=0
    平面法向量朝上(z轴正方向)的视为地面。

    Args:
        pcd: 点云
        distance_threshold: 点到平面的距离阈值(米)
        ransac_n: RANSAC 采样点数
        num_iterations: 迭代次数

    Returns:
        (ground_pcd, non_ground_pcd, plane_model)
        plane_model: [a, b, c, d]
    """
    plane_model, inliers = pcd.segment_plane(
        distance_threshold=distance_threshold,
        ransac_n=ransac_n,
        num_iterations=num_iterations
    )
    ground = pcd.select_by_index(inliers)
    non_ground = pcd.select_by_index(inliers, invert=True)

    # 确保法向量朝上(c>0),否则翻转
    a, b, c, d = plane_model
    if c < 0:
        plane_model = [-a, -b, -c, -d]

    return ground, non_ground, plane_model


def pointcloud_to_array(pcd) -> np.ndarray:
    """点云转 numpy 数组 (N, 3)"""
    return np.asarray(pcd.points)


def array_to_pointcloud(points: np.ndarray):
    """numpy 数组转点云"""
    import open3d as o3d
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    return pcd
