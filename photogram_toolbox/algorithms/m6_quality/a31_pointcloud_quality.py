"""A31 点云质量自动评定

评估稠密点云质量:
    1. 点数/密度
    2. 空间分布完整性
    3. 噪声水平估计
    4. 边缘完整性
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A31PointcloudQuality(Algorithm):
    """A31 点云质量自动评定"""

    @staticmethod
    def name() -> str:
        return "a31_pointcloud_quality"

    @staticmethod
    def display_name() -> str:
        return "A31 点云质量自动评定"

    @staticmethod
    def group() -> str:
        return "M6 质量评定"

    @staticmethod
    def group_id() -> str:
        return "m6"

    @staticmethod
    def short_help() -> str:
        return "评估点云密度/分布/噪声/完整性"

    @staticmethod
    def can_execute() -> bool:
        try:
            import open3d
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 点云路径 (str, .ply)
        """
        ply_path = input_data
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")
        if not ply_path or not os.path.exists(ply_path):
            logger.error(f"点云无效: {ply_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"点云无效: {ply_path}")

        output_report = context.param("output_report",
                                       ply_path.replace(".ply", "_quality.json"))
        logger.debug(f"输出报告路径: {output_report}")

        import open3d as o3d

        # 1. 加载点云
        feedback.set_progress_text("加载点云...")
        logger.timing_start("load_pointcloud")
        pcd = o3d.io.read_point_cloud(ply_path)
        points = np.asarray(pcd.points)
        n_points = len(points)
        logger.timing_end("load_pointcloud")
        logger.debug(f"加载点数: {n_points}")

        if n_points == 0:
            logger.error("点云为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="点云为空")

        feedback.push_info(f"点数: {n_points}")
        feedback.set_progress(20)

        # 2. 空间分布
        feedback.set_progress_text("分析空间分布...")
        logger.timing_start("spatial_distribution")
        bounds_min = points.min(axis=0)
        bounds_max = points.max(axis=0)
        extent = bounds_max - bounds_min
        volume = np.prod(extent) if np.all(extent > 0) else 1
        density = n_points / volume if volume > 0 else 0
        logger.timing_end("spatial_distribution")
        logger.debug(f"空间分布 density={density:.2f} pts/m³")

        feedback.push_info(f"范围: {extent[0]:.1f} x {extent[1]:.1f} x {extent[2]:.1f} m")
        feedback.push_info(f"密度: {density:.2f} pts/m³")
        feedback.set_progress(40)

        # 3. 噪声估计(邻域距离标准差)
        feedback.set_progress_text("估计噪声水平...")
        logger.timing_start("noise_estimate")
        # 随机采样点计算邻域距离
        sample_size = min(1000, n_points)
        sample_idx = np.random.choice(n_points, sample_size, replace=False)
        sample_points = points[sample_idx]

        from scipy.spatial import cKDTree
        tree = cKDTree(points)
        dists, _ = tree.query(sample_points, k=2)  # k=2 排除自身

        nn_dist = dists[:, 1]  # 最近邻距离
        mean_nn_dist = float(np.mean(nn_dist))
        std_nn_dist = float(np.std(nn_dist))
        median_nn_dist = float(np.median(nn_dist))
        logger.timing_end("noise_estimate")
        logger.debug(f"噪声 mean_nn_dist={mean_nn_dist:.4f}, std={std_nn_dist:.4f}")

        feedback.push_info(f"平均邻近距离: {mean_nn_dist:.4f}m")
        feedback.set_progress(60)

        # 4. 均匀性(体素网格填充率)
        feedback.set_progress_text("分析均匀性...")
        logger.timing_start("uniformity")
        voxel_size = max(extent) / 50  # 50格
        voxel_coords = np.floor(points / voxel_size).astype(int)
        unique_voxels = np.unique(voxel_coords, axis=0)
        total_voxels = np.prod(np.ceil(extent / voxel_size).astype(int))
        fill_rate = len(unique_voxels) / total_voxels if total_voxels > 0 else 0
        logger.timing_end("uniformity")
        logger.debug(f"均匀性 fill_rate={fill_rate*100:.1f}%")

        feedback.push_info(f"体素填充率: {fill_rate*100:.1f}%")
        feedback.set_progress(80)

        # 5. 质量评分
        density_score = min(density / 10 * 100, 100)  # 10 pts/m³ 为满分
        uniformity_score = fill_rate * 100
        noise_score = max(100 - std_nn_dist / mean_nn_dist * 100, 0) if mean_nn_dist > 0 else 0

        overall_score = (density_score * 0.4 + uniformity_score * 0.4 + noise_score * 0.2)

        report = {
            "point_count": n_points,
            "spatial_distribution": {
                "bounds_min": bounds_min.tolist(),
                "bounds_max": bounds_max.tolist(),
                "extent_m": extent.tolist(),
                "volume_m3": float(volume),
                "density_pts_per_m3": float(density),
            },
            "noise": {
                "mean_nn_distance": mean_nn_dist,
                "std_nn_distance": std_nn_dist,
                "median_nn_distance": median_nn_dist,
            },
            "uniformity": {
                "voxel_size": float(voxel_size),
                "filled_voxels": len(unique_voxels),
                "total_voxels": int(total_voxels),
                "fill_rate": float(fill_rate),
            },
            "scores": {
                "density": float(density_score),
                "uniformity": float(uniformity_score),
                "noise": float(noise_score),
                "overall": float(overall_score),
            }
        }

        logger.timing_start("write_report")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.timing_end("write_report")
        logger.debug(f"报告已写入: {output_report}")

        feedback.set_progress(100)
        feedback.push_info(f"质量评分: {overall_score:.1f}/100")

        logger.timing_end("total")
        result = AlgoResult(
            status=0,
            message=f"点云质量评定完成, 评分 {overall_score:.1f}/100",
            outputs=[output_report],
            metadata=report
        )
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
