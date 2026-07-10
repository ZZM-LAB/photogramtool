"""A04 控制点自动识别与配准

将SfM重建的局部坐标系对齐到大地坐标系:
    1. 读取控制点文件(image_name, x, y, z)
    2. 在影像中识别控制点像点坐标
    3. 通过相似变换将重建结果对齐到控制点
    4. 输出带绝对坐标的稀疏模型
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A04ControlPointRegistration(Algorithm):
    """A04 控制点自动识别与配准"""

    @staticmethod
    def name() -> str:
        return "a04_control_point_registration"

    @staticmethod
    def display_name() -> str:
        return "A04 控制点自动识别与配准"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return "读取控制点,将重建结果对齐到大地坐标系"

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
            input_data: 稀疏重建目录 (str, 含 cameras.bin/images.bin/points3D.bin)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        sparse_dir = input_data
        if not sparse_dir or not os.path.isdir(sparse_dir):
            logger.error(f"稀疏重建目录无效: {sparse_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"稀疏重建目录无效: {sparse_dir}")

        # 控制点文件路径
        gcp_file = context.param("gcp_file", "")
        if not gcp_file or not os.path.exists(gcp_file):
            logger.error(f"控制点文件不存在: {gcp_file}")
            logger.timing_end("total")
            return AlgoResult(
                status=1,
                message=f"控制点文件不存在: {gcp_file}"
            )

        feedback.push_info(f"稀疏重建目录: {sparse_dir}")
        feedback.push_info(f"控制点文件: {gcp_file}")
        logger.debug(f"稀疏重建目录: {sparse_dir}, 控制点文件: {gcp_file}")

        # 读取控制点
        feedback.set_progress_text("读取控制点...")
        logger.debug("开始读取控制点")
        logger.timing_start("read_gcp")
        locations = {}
        with open(gcp_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 4:
                    # 格式: image_name x y z
                    locations[parts[0]] = [float(parts[1]),
                                           float(parts[2]),
                                           float(parts[3])]
        logger.timing_end("read_gcp")
        feedback.push_info(f"读取到 {len(locations)} 个控制点")
        logger.debug(f"读取到 {len(locations)} 个控制点")
        feedback.set_progress(30)

        if not locations:
            logger.error("控制点文件为空或格式错误")
            logger.timing_end("total")
            return AlgoResult(status=1, message="控制点文件为空或格式错误")

        # 对齐
        import pycolmap
        feedback.set_progress_text("对齐到大地坐标系...")
        logger.debug("开始对齐到大地坐标系")
        logger.timing_start("align_to_locations")
        recon = pycolmap.Reconstruction(sparse_dir)
        pycolmap.align_reconstruction_to_locations(recon, locations)
        recon.write(sparse_dir)
        logger.timing_end("align_to_locations")
        logger.debug("对齐到大地坐标系完成")

        feedback.set_progress(100)
        feedback.push_info("控制点配准完成")

        result = AlgoResult(
            status=0,
            message=f"控制点配准完成,使用 {len(locations)} 个控制点",
            outputs=[sparse_dir],
            metadata={
                "sparse_dir": sparse_dir,
                "gcp_count": len(locations),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
