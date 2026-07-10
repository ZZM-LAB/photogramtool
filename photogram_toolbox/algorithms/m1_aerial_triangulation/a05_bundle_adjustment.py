"""A05 全局Bundle Adjustment平差

对整个重建结果执行全局光束平差,同时优化:
    - 所有相机外方位元素(位姿)
    - 所有3D点坐标
    - (可选)相机内方位元素
最小化所有观测的重投影误差。
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A05GlobalBundleAdjustment(Algorithm):
    """A05 全局Bundle Adjustment平差"""

    @staticmethod
    def name() -> str:
        return "a05_global_bundle_adjustment"

    @staticmethod
    def display_name() -> str:
        return "A05 全局Bundle Adjustment平差"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return "全局光束平差,优化相机位姿和3D点坐标,最小化重投影误差"

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
            input_data: 稀疏重建目录 (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        sparse_dir = input_data
        if not sparse_dir or not os.path.isdir(sparse_dir):
            logger.error(f"稀疏重建目录无效: {sparse_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"稀疏重建目录无效: {sparse_dir}")

        feedback.push_info(f"稀疏重建目录: {sparse_dir}")
        logger.debug(f"稀疏重建目录: {sparse_dir}")

        import pycolmap

        # 加载重建
        feedback.set_progress_text("加载重建结果...")
        logger.debug("开始加载重建结果")
        logger.timing_start("load_reconstruction")
        recon = pycolmap.Reconstruction(sparse_dir)
        logger.timing_end("load_reconstruction")
        feedback.push_info(f"影像数: {len(recon.images)}, 3D点数: {len(recon.points3D)}")
        logger.debug(f"加载重建完成, 影像数: {len(recon.images)}, 3D点数: {len(recon.points3D)}")
        feedback.set_progress(30)

        # 配置光束平差
        feedback.set_progress_text("执行全局光束平差...")
        opts = pycolmap.BundleAdjustmentOptions()
        opts.refine_focal_length = context.param("refine_focal", True)
        opts.refine_principal_point = context.param("refine_pp", False)
        opts.refine_extra_params = context.param("refine_distortion", True)
        logger.debug(f"光束平差参数: refine_focal={opts.refine_focal_length}, "
                     f"refine_pp={opts.refine_principal_point}, "
                     f"refine_distortion={opts.refine_extra_params}")

        ba = pycolmap.BundleAdjuster(opts)
        logger.debug("开始执行光束平差")
        logger.timing_start("bundle_adjustment")
        summary = ba.solve(recon)
        logger.timing_end("bundle_adjustment")
        logger.debug(f"光束平差执行完成, summary={summary}")
        feedback.set_progress(80)

        # 保存
        feedback.set_progress_text("保存优化结果...")
        logger.debug("开始保存优化结果")
        logger.timing_start("save_reconstruction")
        recon.write(sparse_dir)
        logger.timing_end("save_reconstruction")
        logger.debug("优化结果保存完成")

        feedback.set_progress(100)
        feedback.push_info("光束平差完成")

        # 统计
        num_images = len(recon.images)
        num_points = len(recon.points3D)

        result = AlgoResult(
            status=0,
            message=f"光束平差完成,影像:{num_images}, 3D点:{num_points}",
            outputs=[sparse_dir],
            metadata={
                "sparse_dir": sparse_dir,
                "num_images": num_images,
                "num_points3d": num_points,
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
