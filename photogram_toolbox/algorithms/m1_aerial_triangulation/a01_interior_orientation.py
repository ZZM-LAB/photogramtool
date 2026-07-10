"""A01 影像自动内定向 - 导入影像并推断相机内方位元素

通过 pycolmap 读取影像 EXIF,自动推断焦距/主点/畸变参数,
建立相机模型并写入数据库。为后续 SfM 流程做准备。
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.colmap_wrapper import (
    ensure_dir, create_database, import_images
)


@REGISTRY.register
class A01InteriorOrientation(Algorithm):
    """A01 影像自动内定向"""

    @staticmethod
    def name() -> str:
        return "a01_interior_orientation"

    @staticmethod
    def display_name() -> str:
        return "A01 影像自动内定向"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return ("读取影像EXIF,自动推断相机内方位元素"
                "(焦距/主点/畸变),建立相机模型")

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
        image_dir = input_data
        if not image_dir or not os.path.isdir(image_dir):
            return AlgoResult(status=1, message=f"影像目录无效: {image_dir}")

        work_dir = context.work_dir or os.path.join(image_dir, "..", "work")
        ensure_dir(work_dir)

        feedback.push_info(f"影像目录: {image_dir}")
        feedback.push_info(f"工作目录: {work_dir}")

        # 1. 创建数据库
        feedback.set_progress_text("创建 COLMAP 数据库...")
        db = create_database(work_dir)
        feedback.set_progress(30)
        feedback.push_info(f"数据库: {db}")

        # 2. 导入影像并推断相机参数
        feedback.set_progress_text("导入影像,推断相机内方位元素...")
        camera_model = context.param("camera_model", "SIMPLE_RADIAL")
        single_camera = context.param("single_camera", True)
        import_images(image_dir, work_dir, camera_model, single_camera)

        feedback.set_progress(100)
        return AlgoResult(
            status=0,
            message=f"内定向完成,相机模型: {camera_model}",
            outputs=[db],
            metadata={
                "work_dir": work_dir,
                "camera_model": camera_model,
                "database": db,
            }
        )
