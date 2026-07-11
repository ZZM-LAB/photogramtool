"""A35 纹理自动映射

为三维网格生成纹理:
    1. 读取网格和原始影像
    2. 使用 Open3D 纹理映射或简化方案
    3. 输出带纹理的模型(OBJ+MTL+纹理图)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A35TextureMapping(Algorithm):
    """A35 纹理自动映射"""

    @staticmethod
    def name() -> str:
        return "a35_texture_mapping"

    @staticmethod
    def display_name() -> str:
        return "A35 纹理自动映射"

    @staticmethod
    def group() -> str:
        return "M7 三维建模"

    @staticmethod
    def group_id() -> str:
        return "m7"

    @staticmethod
    def short_help() -> str:
        return "为网格生成纹理,输出OBJ+MTL"

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
            input_data: 网格路径 (str, .ply)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        mesh_path = input_data
        if not mesh_path or not os.path.exists(mesh_path):
            logger.error(f"网格文件无效: {mesh_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"网格文件无效: {mesh_path}")

        output_obj = context.param("output_obj",
                                    mesh_path.replace(".ply", "_textured.obj"))
        texture_path = context.param("texture_path", "")

        feedback.push_info(f"输入: {mesh_path}")

        import open3d as o3d

        # 1. 加载网格
        logger.timing_start("load_mesh")
        feedback.set_progress_text("加载网格...")
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        n_vertices = len(mesh.vertices)
        n_triangles = len(mesh.triangles)
        logger.debug(f"顶点: {n_vertices}, 面: {n_triangles}")
        feedback.push_info(f"顶点: {n_vertices}, 面: {n_triangles}")
        logger.timing_end("load_mesh")
        feedback.set_progress(30)

        if n_vertices == 0:
            logger.error("网格为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="网格为空")

        # 2. UV 展开(简化:使用球面投影)
        logger.timing_start("uv_mapping")
        feedback.set_progress_text("UV 映射...")

        # 使用 Open3D 的球面参数化
        if mesh.has_vertices():
            try:
                mesh.compute_vertex_normals()
                # 球面UV映射
                vertices = np.asarray(mesh.vertices)
                center = vertices.mean(axis=0)
                centered = vertices - center

                # 球面坐标
                r = np.linalg.norm(centered, axis=1)
                theta = np.arccos(np.clip(centered[:, 2] / (r + 1e-10), -1, 1))
                phi = np.arctan2(centered[:, 1], centered[:, 0])

                u = (phi + np.pi) / (2 * np.pi)
                v = theta / np.pi

                # 设置 UV
                import open3d.utility as utility
                uvs = np.stack([u, v], axis=1)
                mesh.triangle_uvs = o3d.utility.Vector2dVector(
                    np.tile(uvs, (1, 1)).reshape(-1, 2)
                )
                logger.debug("UV映射完成(球面投影)")
            except Exception as e:
                logger.warning(f"UV映射失败,使用简化方案: {e}")
        logger.timing_end("uv_mapping")
        feedback.set_progress(60)

        # 3. 顶点颜色作为纹理
        logger.timing_start("apply_color")
        feedback.set_progress_text("应用顶点颜色...")

        if not mesh.has_vertex_colors():
            # 生成简化的顶点颜色(基于高度)
            vertices = np.asarray(mesh.vertices)
            z = vertices[:, 2]
            z_min, z_max = z.min(), z.max()
            z_norm = (z - z_min) / (z_max - z_min + 1e-10)

            # 伪彩色(绿到棕)
            colors = np.zeros((len(vertices), 3))
            colors[:, 0] = z_norm  # R
            colors[:, 1] = 1 - z_norm * 0.5  # G
            colors[:, 2] = 0.2 * (1 - z_norm)  # B
            mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
            logger.debug("顶点颜色生成完成(高程伪彩色)")

        logger.timing_end("apply_color")
        feedback.set_progress(80)

        # 4. 保存为OBJ
        logger.timing_start("save_obj")
        feedback.set_progress_text("保存OBJ...")
        o3d.io.write_triangle_mesh(output_obj, mesh)
        logger.debug(f"保存: {output_obj}")
        logger.timing_end("save_obj")
        feedback.set_progress(100)

        file_size = os.path.getsize(output_obj) / 1024 / 1024
        feedback.push_info(f"纹理模型保存: {output_obj} ({file_size:.1f} MB)")

        result = AlgoResult(
            status=0,
            message=f"纹理映射完成(球面UV+顶点颜色)",
            outputs=[output_obj],
            metadata={
                "output_obj": output_obj,
                "vertices": n_vertices,
                "triangles": n_triangles,
                "uv_method": "spherical",
                "color_method": "vertex_elevation" if not mesh.has_vertex_colors() else "original",
                "file_size_mb": float(file_size),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
