"""A07 MVS多视角密集匹配

调用 COLMAP CUDA 的 patch_match_stereo + stereo_fusion,
将去畸变影像转为稠密点云。

流程:
    去畸变影像 → patch_match_stereo(深度图) → stereo_fusion(稠密点云)
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.colmap_cli import patch_match_stereo, stereo_fusion


@REGISTRY.register
class A07MVSDenseMatching(Algorithm):
    """A07 MVS多视角密集匹配"""

    @staticmethod
    def name() -> str:
        return "a07_mvs_dense_matching"

    @staticmethod
    def display_name() -> str:
        return "A07 MVS多视角密集匹配"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "Patch Match Stereo 稠密匹配,生成稠密点云"

    @staticmethod
    def can_execute() -> bool:
        try:
            from photogram_toolbox.core.colmap_cli import find_colmap
            find_colmap()
            return True
        except (FileNotFoundError, ImportError):
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: dense 工作目录 (str, A06 undistort_images 的输出)
        """
        dense_dir = input_data
        if not dense_dir or not os.path.isdir(dense_dir):
            return AlgoResult(status=1, message=f"工作目录无效: {dense_dir}")

        output_ply = context.param("output_ply",
                                    os.path.join(dense_dir, "fused.ply"))

        feedback.push_info(f"输入目录: {dense_dir}")
        feedback.push_info(f"输出点云: {output_ply}")

        # 1. Patch Match Stereo (生成深度图)
        feedback.set_progress_text("执行 Patch Match Stereo 稠密匹配...")
        feedback.set_progress(20)
        try:
            patch_match_stereo(dense_dir)
        except RuntimeError as e:
            return AlgoResult(status=1, message=f"MVS匹配失败: {e}")
        feedback.set_progress(60)
        feedback.push_info("深度图生成完成")

        # 2. Stereo Fusion (融合为点云)
        feedback.set_progress_text("融合深度图为稠密点云...")
        try:
            stereo_fusion(dense_dir, output_ply)
        except RuntimeError as e:
            return AlgoResult(status=1, message=f"点云融合失败: {e}")

        if not os.path.exists(output_ply):
            return AlgoResult(status=1, message="融合失败,未生成点云文件")

        feedback.set_progress(100)
        feedback.push_info(f"稠密点云生成完成: {output_ply}")

        return AlgoResult(
            status=0,
            message="MVS稠密匹配完成",
            outputs=[output_ply],
            metadata={
                "dense_dir": dense_dir,
                "pointcloud": output_ply,
            }
        )
