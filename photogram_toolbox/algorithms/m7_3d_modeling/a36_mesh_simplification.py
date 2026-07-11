"""A36 三维模型自动简化

使用边折叠(Edge Collapse)简化网格:
    1. 读取网格
    2. 计算简化目标(面数比例)
    3. Open3D 简化
    4. 输出简化网格
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A36MeshSimplification(Algorithm):
    """A36 三维模型自动简化"""

    @staticmethod
    def name() -> str:
        return "a36_mesh_simplification"

    @staticmethod
    def display_name() -> str:
        return "A36 三维模型自动简化"

    @staticmethod
    def group() -> str:
        return "M7 三维建模"

    @staticmethod
    def group_id() -> str:
        return "m7"

    @staticmethod
    def short_help() -> str:
        return "边折叠简化网格,降低面数"

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
            input_data: 网格路径 (str, .ply/.obj)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        mesh_path = input_data
        if not mesh_path or not os.path.exists(mesh_path):
            logger.error(f"网格文件无效: {mesh_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"网格文件无效: {mesh_path}")

        output_path = context.param("output_path",
                                     mesh_path.replace(".ply", "_simplified.ply")
                                     .replace(".obj", "_simplified.obj"))
        target_ratio = context.param("target_ratio", 0.5)  # 目标面数比例
        target_triangles = context.param("target_triangles", 0)  # 0=按比例

        feedback.push_info(f"输入: {mesh_path}")
        feedback.push_info(f"目标比例: {target_ratio}")

        import open3d as o3d

        # 1. 加载
        logger.timing_start("load_mesh")
        feedback.set_progress_text("加载网格...")
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        original_triangles = len(mesh.triangles)
        original_vertices = len(mesh.vertices)
        logger.debug(f"原始: {original_vertices}顶点, {original_triangles}面")
        feedback.push_info(f"原始: {original_vertices}顶点, {original_triangles}面")
        logger.timing_end("load_mesh")
        feedback.set_progress(20)

        if original_triangles == 0:
            logger.error("网格为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="网格为空")

        # 2. 计算目标面数
        if target_triangles > 0:
            target = target_triangles
        else:
            target = int(original_triangles * target_ratio)

        feedback.push_info(f"目标面数: {target}")
        feedback.set_progress(30)

        # 3. 简化
        logger.timing_start("simplify")
        feedback.set_progress_text("边折叠简化...")
        mesh_simplified = mesh.simplify_quadric_decimation(target)
        simplified_triangles = len(mesh_simplified.triangles)
        simplified_vertices = len(mesh_simplified.vertices)
        logger.debug(f"简化后: {simplified_vertices}顶点, {simplified_triangles}面")
        logger.timing_end("simplify")
        feedback.set_progress(80)

        # 4. 保存
        logger.timing_start("save")
        feedback.set_progress_text("保存简化网格...")
        mesh_simplified.compute_vertex_normals()
        o3d.io.write_triangle_mesh(output_path, mesh_simplified)
        logger.timing_end("save")
        feedback.set_progress(100)

        actual_ratio = simplified_triangles / original_triangles
        file_size = os.path.getsize(output_path) / 1024 / 1024
        feedback.push_info(f"简化后: {simplified_vertices}顶点, {simplified_triangles}面")
        feedback.push_info(f"实际比例: {actual_ratio:.2%}")

        result = AlgoResult(
            status=0,
            message=f"网格简化完成: {original_triangles}→{simplified_triangles}面 ({actual_ratio:.1%})",
            outputs=[output_path],
            metadata={
                "output_path": output_path,
                "original_vertices": original_vertices,
                "original_triangles": original_triangles,
                "simplified_vertices": simplified_vertices,
                "simplified_triangles": simplified_triangles,
                "actual_ratio": float(actual_ratio),
                "file_size_mb": float(file_size),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
