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
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


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
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        input_ply = input_data
        if not input_ply or not os.path.exists(input_ply):
            logger.error(f"点云文件无效: {input_ply}")
            result = AlgoResult(status=1, message=f"点云文件无效: {input_ply}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        output_ply = context.param("output_ply",
                                    input_ply.replace(".ply", "_denoised.ply"))

        nb_neighbors = context.param("nb_neighbors", 20)
        std_ratio = context.param("std_ratio", 2.0)

        feedback.push_info(f"输入: {input_ply}")
        feedback.push_info(f"参数: nb_neighbors={nb_neighbors}, std_ratio={std_ratio}")
        logger.debug(f"参数: nb_neighbors={nb_neighbors}, std_ratio={std_ratio}, output_ply={output_ply}")

        # 加载点云
        feedback.set_progress_text("加载点云...")
        logger.timing_start("load_pointcloud")
        pcd = load_pointcloud(input_ply)
        original_count = len(pcd.points)
        logger.timing_end("load_pointcloud")
        feedback.push_info(f"原始点数: {original_count}")
        logger.debug(f"原始点数: {original_count}")
        feedback.set_progress(30)

        # 去噪
        feedback.set_progress_text("执行统计离群点去除...")
        logger.timing_start("sor_denoise")
        cleaned, removed = statistical_outlier_removal(
            pcd, nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )
        logger.timing_end("sor_denoise")
        feedback.set_progress(80)

        # 保存
        feedback.set_progress_text("保存去噪结果...")
        logger.timing_start("save_pointcloud")
        save_pointcloud(cleaned, output_ply)
        logger.timing_end("save_pointcloud")

        cleaned_count = len(cleaned.points)
        removed_count = len(removed.points)
        removal_rate = removed_count / original_count * 100 if original_count else 0

        feedback.set_progress(100)
        feedback.push_info(f"去噪完成: 保留 {cleaned_count}, 去除 {removed_count} ({removal_rate:.1f}%)")
        logger.debug(f"去噪结果: 保留 {cleaned_count}, 去除 {removed_count} ({removal_rate:.1f}%)")

        result = AlgoResult(
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
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
