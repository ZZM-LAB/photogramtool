"""A03 逐步增量SfM重建

基于特征匹配结果,执行增量式运动恢复结构:
    1. 选择初始影像对
    2. 三角化初始点云
    3. 逐步注册新影像(PnP)
    4. 局部/全局光束平差
    5. 输出稀疏点云+相机位姿
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.colmap_wrapper import (
    ensure_dir, database_path, incremental_mapping
)
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A03IncrementalSfM(Algorithm):
    """A03 逐步增量SfM重建"""

    @staticmethod
    def name() -> str:
        return "a03_incremental_sfm"

    @staticmethod
    def display_name() -> str:
        return "A03 逐步增量SfM重建"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return "增量式运动恢复结构,输出稀疏点云和相机外方位元素"

    @staticmethod
    def can_execute() -> bool:
        try:
            import pycolmap
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 影像目录路径 (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        image_dir = input_data
        if not image_dir or not os.path.isdir(image_dir):
            logger.error(f"影像目录无效: {image_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"影像目录无效: {image_dir}")

        work_dir = context.work_dir or os.path.dirname(image_dir)
        db = database_path(work_dir)
        if not os.path.exists(db):
            logger.error(f"数据库不存在: {db},请先运行A01/A02")
            logger.timing_end("total")
            return AlgoResult(
                status=1,
                message=f"数据库不存在: {db},请先运行A01/A02"
            )

        sparse_dir = context.param("sparse_dir",
                                   os.path.join(work_dir, "sparse"))

        feedback.push_info(f"影像目录: {image_dir}")
        feedback.push_info(f"输出目录: {sparse_dir}")
        logger.debug(f"影像目录: {image_dir}, 输出目录: {sparse_dir}, 工作目录: {work_dir}")

        # 增量式 SfM
        feedback.set_progress_text("执行增量式SfM重建...")
        logger.debug("开始增量式SfM重建")
        logger.timing_start("incremental_mapping")
        output_dir = incremental_mapping(work_dir, image_dir, sparse_dir)
        logger.timing_end("incremental_mapping")
        logger.debug(f"增量式SfM重建完成, output_dir={output_dir}")

        # 检查结果
        recon_dir = os.path.join(output_dir, "0")
        if not os.path.exists(recon_dir):
            logger.error(f"SfM重建失败,未生成稀疏模型, recon_dir={recon_dir}")
            logger.timing_end("total")
            return AlgoResult(
                status=1,
                message="SfM重建失败,未生成稀疏模型"
            )

        feedback.set_progress(100)
        feedback.push_info(f"稀疏重建完成: {recon_dir}")
        logger.debug(f"稀疏重建完成: {recon_dir}")

        result = AlgoResult(
            status=0,
            message="增量SfM重建完成",
            outputs=[recon_dir],
            metadata={
                "sparse_dir": recon_dir,
                "work_dir": work_dir,
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
