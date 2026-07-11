"""A37 三维模型格式自动转换

支持多种3D格式互转:
    PLY ↔ OBJ ↔ STL ↔ GLTF/OBJ
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A37ModelConversion(Algorithm):
    """A37 三维模型格式自动转换"""

    @staticmethod
    def name() -> str:
        return "a37_model_conversion"

    @staticmethod
    def display_name() -> str:
        return "A37 三维模型格式自动转换"

    @staticmethod
    def group() -> str:
        return "M7 三维建模"

    @staticmethod
    def group_id() -> str:
        return "m7"

    @staticmethod
    def short_help() -> str:
        return "PLY/OBJ/STL/GLTF格式互转"

    @staticmethod
    def can_execute() -> bool:
        try:
            import open3d
            return True
        except ImportError:
            return False

    # 支持的格式
    SUPPORTED_FORMATS = {
        ".ply": "Stanford PLY",
        ".obj": "Wavefront OBJ",
        ".stl": "STL",
        ".gltf": "glTF",
        ".glb": "glTF Binary",
        ".off": "OFF",
    }

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 输入网格路径 (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        mesh_path = input_data
        if not mesh_path or not os.path.exists(mesh_path):
            logger.error(f"网格文件无效: {mesh_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"网格文件无效: {mesh_path}")

        output_format = context.param("output_format", ".obj").lower()
        if not output_format.startswith("."):
            output_format = "." + output_format

        if output_format not in self.SUPPORTED_FORMATS:
            logger.error(f"不支持的格式: {output_format}")
            logger.timing_end("total")
            return AlgoResult(status=1,
                              message=f"不支持格式: {output_format}, 支持: {list(self.SUPPORTED_FORMATS.keys())}")

        # 输出路径
        base = os.path.splitext(mesh_path)[0]
        output_path = base + "_converted" + output_format

        feedback.push_info(f"输入: {mesh_path}")
        feedback.push_info(f"输出格式: {output_format} ({self.SUPPORTED_FORMATS[output_format]})")

        import open3d as o3d

        # 1. 加载
        logger.timing_start("load")
        feedback.set_progress_text("加载网格...")
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        n_vertices = len(mesh.vertices)
        n_triangles = len(mesh.triangles)
        logger.debug(f"顶点: {n_vertices}, 面: {n_triangles}")
        logger.timing_end("load")
        feedback.set_progress(40)

        if n_vertices == 0:
            logger.error("网格为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="网格为空")

        # 2. 确保有法向量
        if not mesh.has_vertex_normals():
            mesh.compute_vertex_normals()

        # 3. 保存
        logger.timing_start("save")
        feedback.set_progress_text(f"转换为 {output_format}...")
        success = o3d.io.write_triangle_mesh(output_path, mesh)
        logger.timing_end("save")

        if not success or not os.path.exists(output_path):
            logger.error(f"保存失败: {output_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"转换失败: {output_format}")

        feedback.set_progress(100)
        file_size = os.path.getsize(output_path) / 1024 / 1024
        feedback.push_info(f"转换完成: {output_path} ({file_size:.1f} MB)")

        result = AlgoResult(
            status=0,
            message=f"格式转换完成: {os.path.splitext(mesh_path)[1]} → {output_format}",
            outputs=[output_path],
            metadata={
                "output_path": output_path,
                "input_format": os.path.splitext(mesh_path)[1],
                "output_format": output_format,
                "vertices": n_vertices,
                "triangles": n_triangles,
                "file_size_mb": float(file_size),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
