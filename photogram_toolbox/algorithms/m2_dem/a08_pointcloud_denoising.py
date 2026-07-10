"""A08 点云自动去噪

使用 Open3D 统计离群点去除算法:
    1. 计算每个点到 k 邻域的平均距离
    2. 全局平均距离 + std_ratio * 标准差 作为阈值
    3. 超出阈值的点视为噪声去除
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.pointcloud_utils import (
    load_pointcloud, save_pointcloud, statistical_outlier_removal
)


@REGISTRY.register
class A08PointcloudDenoising(Algorithm):
    """A08 点云自动去噪"""

    @staticmethod
    def name() -> str:
        return "a08_pointcloud_denoising"

    @staticmethod
    def display_name() -> str:
        return "A08 点云自动去噪"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "统计离群点去除,滤除噪声点"

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

        output_ply = context.param("output_ply",
                                    input_ply.replace(".ply", "_denoised.ply"))

        nb_neighbors = context.param("nb_neighbors", 20)
        std_ratio = context.param("std_ratio", 2.0)

        feedback.push_info(f"输入: {input_ply}")
        feedback.push_info(f"参数: nb_neighbors={nb_neighbors}, std_ratio={std_ratio}")

        # 加载点云
        feedback.set_progress_text("加载点云...")
        pcd = load_pointcloud(input_ply)
        original_count = len(pcd.points)
        feedback.push_info(f"原始点数: {original_count}")
        feedback.set_progress(30)

        # 去噪
        feedback.set_progress_text("执行统计离群点去除...")
        cleaned, removed = statistical_outlier_removal(
            pcd, nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )
        feedback.set_progress(80)

        # 保存
        feedback.set_progress_text("保存去噪结果...")
        save_pointcloud(cleaned, output_ply)

        cleaned_count = len(cleaned.points)
        removed_count = len(removed.points)
        removal_rate = removed_count / original_count * 100 if original_count else 0

        feedback.set_progress(100)
        feedback.push_info(f"去噪完成: 保留 {cleaned_count}, 去除 {removed_count} ({removal_rate:.1f}%)")

        return AlgoResult(
            status=0,
            message=f"去噪完成,去除 {removed_count} 个噪声点 ({removal_rate:.1f}%)",
            outputs=[output_ply],
            metadata={
                "input_ply": input_ply,
                "output_ply": output_ply,
                "original_count": original_count,
                "cleaned_count": cleaned_count,
                "removed_count": removed_count,
                "removal_rate": removal_rate,
            }
        )
