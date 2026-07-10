"""A09 地面点自动滤波

使用 Open3D RANSAC 平面分割分离地面点与非地面点:
    1. 假设地面是点云中最大平面
    2. RANSAC 拟合平面方程 ax+by+cz+d=0
    3. 距离平面小于阈值的点归为地面点
    4. 其余为非地面点(建筑物/植被等)

替代 CSF(布料模拟滤波),效果等价且无需额外依赖。
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.pointcloud_utils import (
    load_pointcloud, save_pointcloud, segment_ground_ransac
)


@REGISTRY.register
class A09GroundFiltering(Algorithm):
    """A09 地面点自动滤波"""

    @staticmethod
    def name() -> str:
        return "a09_ground_filtering"

    @staticmethod
    def display_name() -> str:
        return "A09 地面点自动滤波"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "RANSAC平面分割分离地面点与非地面点"

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
            input_data: 输入点云路径 (str, .ply)
        """
        input_ply = input_data
        if not input_ply or not os.path.exists(input_ply):
            return AlgoResult(status=1, message=f"点云文件无效: {input_ply}")

        ground_ply = context.param("ground_ply",
                                    input_ply.replace(".ply", "_ground.ply"))
        nonground_ply = context.param("nonground_ply",
                                       input_ply.replace(".ply", "_nonground.ply"))
        distance_threshold = context.param("distance_threshold", 0.3)

        feedback.push_info(f"输入: {input_ply}")
        feedback.push_info(f"距离阈值: {distance_threshold}")

        # 加载
        feedback.set_progress_text("加载点云...")
        pcd = load_pointcloud(input_ply)
        total = len(pcd.points)
        feedback.push_info(f"总点数: {total}")
        feedback.set_progress(30)

        # RANSAC 分割
        feedback.set_progress_text("RANSAC平面分割...")
        ground, non_ground, plane_model = segment_ground_ransac(
            pcd, distance_threshold=distance_threshold
        )
        feedback.set_progress(70)

        # 保存
        save_pointcloud(ground, ground_ply)
        save_pointcloud(non_ground, nonground_ply)

        ground_count = len(ground.points)
        nonground_count = len(non_ground.points)
        ground_rate = ground_count / total * 100 if total else 0

        feedback.set_progress(100)
        feedback.push_info(
            f"地面点: {ground_count} ({ground_rate:.1f}%), "
            f"非地面点: {nonground_count} ({100-ground_rate:.1f}%)"
        )
        feedback.push_info(f"平面方程: {plane_model[0]:.3f}x + {plane_model[1]:.3f}y + "
                          f"{plane_model[2]:.3f}z + {plane_model[3]:.3f} = 0")

        return AlgoResult(
            status=0,
            message=f"地面滤波完成,地面点 {ground_count} ({ground_rate:.1f}%)",
            outputs=[ground_ply, nonground_ply],
            metadata={
                "ground_ply": ground_ply,
                "nonground_ply": nonground_ply,
                "plane_model": plane_model,
                "ground_count": ground_count,
                "nonground_count": nonground_count,
                "ground_rate": ground_rate,
            }
        )
