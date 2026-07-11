"""A34 三维网格自动重建

使用 Poisson 表面重建从点云生成三角网格:
    1. 读取稠密点云
    2. 估计法向量
    3. Poisson 重建
    4. 顶点颜色传递
    5. 输出网格(PLY)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A34MeshReconstruction(Algorithm):
    """A34 三维网格自动重建"""

    @staticmethod
    def name() -> str:
        return "a34_mesh_reconstruction"

    @staticmethod
    def display_name() -> str:
        return "A34 三维网格自动重建"

    @staticmethod
    def group() -> str:
        return "M7 三维建模"

    @staticmethod
    def group_id() -> str:
        return "m7"

    @staticmethod
    def short_help() -> str:
        return "Poisson表面重建,点云→三角网格"

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
            input_data: 点云路径 (str, .ply)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        ply_path = input_data
        if not ply_path or not os.path.exists(ply_path):
            logger.error(f"点云文件无效: {ply_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"点云文件无效: {ply_path}")

        output_mesh = context.param("output_mesh",
                                     ply_path.replace(".ply", "_mesh.ply"))
        octree_depth = context.param("octree_depth", 9)
        knn_normals = context.param("knn_normals", 30)

        feedback.push_info(f"输入: {ply_path}")
        feedback.push_info(f"Poisson octree_depth: {octree_depth}")

        import open3d as o3d

        # 1. 加载点云
        logger.timing_start("load_pointcloud")
        feedback.set_progress_text("加载点云...")
        pcd = o3d.io.read_point_cloud(ply_path)
        n_points = len(pcd.points)
        logger.debug(f"点数: {n_points}")
        feedback.push_info(f"点数: {n_points}")
        logger.timing_end("load_pointcloud")
        feedback.set_progress(20)

        if n_points == 0:
            logger.error("点云为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="点云为空")

        # 2. 估计法向量
        logger.timing_start("estimate_normals")
        feedback.set_progress_text("估计法向量...")
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(
                radius=0.1, max_nn=knn_normals
            )
        )
        # 法向量定向(一致朝外)
        pcd.orient_normals_towards_camera_location(
            camera_location=np.array([0, 0, 1000])
        )
        logger.debug("法向量估计完成")
        logger.timing_end("estimate_normals")
        feedback.set_progress(40)

        # 3. Poisson 重建
        logger.timing_start("poisson_reconstruction")
        feedback.set_progress_text("Poisson 表面重建...")
        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=octree_depth
        )
        n_vertices = len(mesh.vertices)
        n_triangles = len(mesh.triangles)
        logger.debug(f"网格顶点: {n_vertices}, 三角面: {n_triangles}")
        feedback.push_info(f"网格顶点: {n_vertices}, 三角面: {n_triangles}")
        logger.timing_end("poisson_reconstruction")
        feedback.set_progress(70)

        # 4. 密度过滤(去除低密度区域)
        logger.timing_start("density_filter")
        feedback.set_progress_text("密度过滤...")
        densities = np.asarray(densities)
        density_threshold = np.percentile(densities, 5)
        vertices_to_remove = densities < density_threshold
        mesh.remove_vertices_by_mask(vertices_to_remove)
        logger.debug(f"过滤后顶点: {len(mesh.vertices)}")
        logger.timing_end("density_filter")
        feedback.set_progress(85)

        # 5. 保存
        logger.timing_start("save_mesh")
        feedback.set_progress_text("保存网格...")
        mesh.compute_vertex_normals()
        o3d.io.write_triangle_mesh(output_mesh, mesh)
        logger.timing_end("save_mesh")
        feedback.set_progress(100)

        file_size = os.path.getsize(output_mesh) / 1024 / 1024
        feedback.push_info(f"网格保存: {output_mesh} ({file_size:.1f} MB)")

        result = AlgoResult(
            status=0,
            message=f"Poisson重建完成, {len(mesh.vertices)}顶点, {len(mesh.triangles)}面",
            outputs=[output_mesh],
            metadata={
                "output_mesh": output_mesh,
                "vertices": len(mesh.vertices),
                "triangles": len(mesh.triangles),
                "octree_depth": octree_depth,
                "file_size_mb": float(file_size),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
