"""A05 全局Bundle Adjustment平差

对整个重建结果执行全局光束平差,同时优化:
    - 所有相机外方位元素(位姿)
    - 所有3D点坐标
    - (可选)相机内方位元素
最小化所有观测的重投影误差。
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


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
        sparse_dir = input_data
        if not sparse_dir or not os.path.isdir(sparse_dir):
            return AlgoResult(status=1, message=f"稀疏重建目录无效: {sparse_dir}")

        feedback.push_info(f"稀疏重建目录: {sparse_dir}")

        import pycolmap

        # 加载重建
        feedback.set_progress_text("加载重建结果...")
        recon = pycolmap.Reconstruction(sparse_dir)
        feedback.push_info(f"影像数: {len(recon.images)}, 3D点数: {len(recon.points3D)}")
        feedback.set_progress(30)

        # 配置光束平差
        feedback.set_progress_text("执行全局光束平差...")
        opts = pycolmap.BundleAdjustmentOptions()
        opts.refine_focal_length = context.param("refine_focal", True)
        opts.refine_principal_point = context.param("refine_pp", False)
        opts.refine_extra_params = context.param("refine_distortion", True)

        ba = pycolmap.BundleAdjuster(opts)
        summary = ba.solve(recon)
        feedback.set_progress(80)

        # 保存
        feedback.set_progress_text("保存优化结果...")
        recon.write(sparse_dir)

        feedback.set_progress(100)
        feedback.push_info("光束平差完成")

        # 统计
        num_images = len(recon.images)
        num_points = len(recon.points3D)

        return AlgoResult(
            status=0,
            message=f"光束平差完成,影像:{num_images}, 3D点:{num_points}",
            outputs=[sparse_dir],
            metadata={
                "sparse_dir": sparse_dir,
                "num_images": num_images,
                "num_points3d": num_points,
            }
        )
