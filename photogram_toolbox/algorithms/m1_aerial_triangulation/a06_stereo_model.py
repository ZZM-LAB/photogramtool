"""A06 立体模型自动生成(影像去畸变)

对原始影像进行去畸变处理,生成核线影像对,
为后续MVS稠密匹配(A07)做准备。

输入: 稀疏重建结果 + 原始影像
输出: 去畸变影像 + 去畸变相机参数
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.colmap_wrapper import ensure_dir, undistort_images


@REGISTRY.register
class A06StereoModelGeneration(Algorithm):
    """A06 立体模型自动生成(影像去畸变)"""

    @staticmethod
    def name() -> str:
        return "a06_stereo_model_generation"

    @staticmethod
    def display_name() -> str:
        return "A06 立体模型自动生成"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return "影像去畸变,生成核线影像对,为MVS稠密匹配做准备"

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

        work_dir = context.work_dir or os.path.dirname(sparse_dir)
        image_dir = context.param("image_dir", "")
        if not image_dir or not os.path.isdir(image_dir):
            return AlgoResult(
                status=1,
                message=f"影像目录无效: {image_dir},请通过image_dir参数指定"
            )

        dense_dir = context.param("dense_dir",
                                   os.path.join(work_dir, "dense"))

        feedback.push_info(f"稀疏重建目录: {sparse_dir}")
        feedback.push_info(f"影像目录: {image_dir}")
        feedback.push_info(f"输出目录: {dense_dir}")

        # 去畸变
        feedback.set_progress_text("执行影像去畸变...")
        output_dir = undistort_images(work_dir, image_dir, sparse_dir, dense_dir)
        feedback.set_progress(80)

        # 检查输出
        if not os.path.exists(output_dir):
            return AlgoResult(status=1, message="去畸变失败,未生成输出")

        feedback.set_progress(100)
        feedback.push_info(f"去畸变完成: {output_dir}")

        return AlgoResult(
            status=0,
            message="立体模型生成完成(影像已去畸变)",
            outputs=[output_dir],
            metadata={
                "dense_dir": output_dir,
                "sparse_dir": sparse_dir,
                "image_dir": image_dir,
            }
        )
