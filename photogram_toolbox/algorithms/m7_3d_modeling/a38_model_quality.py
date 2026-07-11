"""A38 三维模型质量自动评定

评估三维网格质量:
    1. 网格完整性(封闭/流形)
    2. 三角形质量(长宽比)
    3. 表面积/体积
    4. 拓扑检查
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A38ModelQualityAssessment(Algorithm):
    """A38 三维模型质量自动评定"""

    @staticmethod
    def name() -> str:
        return "a38_model_quality"

    @staticmethod
    def display_name() -> str:
        return "A38 三维模型质量自动评定"

    @staticmethod
    def group() -> str:
        return "M7 三维建模"

    @staticmethod
    def group_id() -> str:
        return "m7"

    @staticmethod
    def short_help() -> str:
        return "网格完整性/三角形质量/表面积体积评估"

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

        output_report = context.param("output_report",
                                       mesh_path.replace(".ply", "_quality.json")
                                       .replace(".obj", "_quality.json"))

        feedback.push_info(f"输入: {mesh_path}")

        import open3d as o3d

        # 1. 加载
        logger.timing_start("load_mesh")
        feedback.set_progress_text("加载网格...")
        mesh = o3d.io.read_triangle_mesh(mesh_path)
        n_vertices = len(mesh.vertices)
        n_triangles = len(mesh.triangles)
        logger.debug(f"顶点: {n_vertices}, 面: {n_triangles}")
        feedback.push_info(f"顶点: {n_vertices}, 面: {n_triangles}")
        logger.timing_end("load_mesh")
        feedback.set_progress(15)

        if n_vertices == 0 or n_triangles == 0:
            logger.error("网格为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="网格为空")

        # 2. 网格完整性
        logger.timing_start("check_manifold")
        feedback.set_progress_text("检查网格完整性...")
        is_watertight = mesh.is_watertight()
        is_orientable = mesh.is_orientable()
        is_manifold = mesh.is_edge_manifold()
        logger.debug(f"watertight={is_watertight}, orientable={is_orientable}, manifold={is_manifold}")
        feedback.push_info(f"封闭: {is_watertight}, 可定向: {is_orientable}, 流形: {is_manifold}")
        logger.timing_end("check_manifold")
        feedback.set_progress(35)

        # 3. 三角形质量
        logger.timing_start("triangle_quality")
        feedback.set_progress_text("计算三角形质量...")
        triangles = np.asarray(mesh.triangles)
        vertices = np.asarray(mesh.vertices)

        # 计算每个三角形的长宽比
        v0 = vertices[triangles[:, 0]]
        v1 = vertices[triangles[:, 1]]
        v2 = vertices[triangles[:, 2]]

        e0 = np.linalg.norm(v1 - v0, axis=1)  # 边长
        e1 = np.linalg.norm(v2 - v1, axis=1)
        e2 = np.linalg.norm(v0 - v2, axis=1)

        edge_lengths = np.stack([e0, e1, e2], axis=1)
        min_edge = edge_lengths.min(axis=1)
        max_edge = edge_lengths.max(axis=1)
        aspect_ratios = max_edge / (min_edge + 1e-10)

        mean_aspect = float(np.mean(aspect_ratios))
        median_aspect = float(np.median(aspect_ratios))
        max_aspect = float(np.max(aspect_ratios))

        # 退化三角形(面积≈0)
        areas = 0.5 * np.linalg.norm(
            np.cross(v1 - v0, v2 - v0), axis=1
        )
        degenerate_count = int(np.sum(areas < 1e-10))

        logger.debug(f"长宽比: mean={mean_aspect:.2f}, max={max_aspect:.2f}, 退化={degenerate_count}")
        feedback.push_info(f"平均长宽比: {mean_aspect:.2f}, 退化三角形: {degenerate_count}")
        logger.timing_end("triangle_quality")
        feedback.set_progress(60)

        # 4. 表面积和体积
        logger.timing_start("surface_volume")
        feedback.set_progress_text("计算表面积/体积...")
        surface_area = float(mesh.get_surface_area())

        if is_watertight:
            volume = float(mesh.get_volume())
        else:
            volume = None
            feedback.push_warning("网格非封闭,无法计算体积")

        logger.debug(f"表面积: {surface_area:.2f}, 体积: {volume}")
        feedback.push_info(f"表面积: {surface_area:.2f} m²")
        if volume is not None:
            feedback.push_info(f"体积: {volume:.2f} m³")
        logger.timing_end("surface_volume")
        feedback.set_progress(80)

        # 5. 边界统计
        logger.timing_start("boundary_stats")
        feedback.set_progress_text("统计边界...")
        # 非流形边
        non_manifold_edges = int(len(mesh.get_non_manifold_edges()))
        # 边界边
        boundary_edges = int(len(mesh.get_non_manifold_edges()))

        # 顶点连接度
        vertex_degrees = np.zeros(n_vertices, dtype=int)
        for tri in triangles:
            vertex_degrees[tri[0]] += 1
            vertex_degrees[tri[1]] += 1
            vertex_degrees[tri[2]] += 1

        mean_degree = float(np.mean(vertex_degrees))
        min_degree = int(np.min(vertex_degrees))
        max_degree = int(np.max(vertex_degrees))
        isolated_vertices = int(np.sum(vertex_degrees == 0))

        logger.debug(f"非流形边: {non_manifold_edges}, 孤立顶点: {isolated_vertices}")
        logger.timing_end("boundary_stats")
        feedback.set_progress(90)

        # 6. 评分
        manifold_score = 100 if (is_manifold and is_orientable) else 50
        watertight_score = 100 if is_watertight else 30

        if mean_aspect < 3:
            quality_score = 100
        elif mean_aspect < 10:
            quality_score = 70
        else:
            quality_score = 40

        degenerate_ratio = degenerate_count / n_triangles
        if degenerate_ratio < 0.01:
            degenerate_score = 100
        elif degenerate_ratio < 0.05:
            degenerate_score = 70
        else:
            degenerate_score = 30

        overall = (manifold_score * 0.3 + watertight_score * 0.2 +
                   quality_score * 0.3 + degenerate_score * 0.2)

        report = {
            "mesh_info": {
                "path": mesh_path,
                "vertices": n_vertices,
                "triangles": n_triangles,
            },
            "topology": {
                "is_watertight": bool(is_watertight),
                "is_orientable": bool(is_orientable),
                "is_manifold": bool(is_manifold),
                "non_manifold_edges": non_manifold_edges,
            },
            "triangle_quality": {
                "mean_aspect_ratio": mean_aspect,
                "median_aspect_ratio": median_aspect,
                "max_aspect_ratio": max_aspect,
                "degenerate_triangles": degenerate_count,
                "degenerate_ratio": float(degenerate_ratio),
            },
            "geometry": {
                "surface_area_m2": surface_area,
                "volume_m3": volume,
            },
            "vertex_stats": {
                "mean_degree": mean_degree,
                "min_degree": min_degree,
                "max_degree": max_degree,
                "isolated_vertices": isolated_vertices,
            },
            "scores": {
                "manifold": float(manifold_score),
                "watertight": float(watertight_score),
                "triangle_quality": float(quality_score),
                "degenerate": float(degenerate_score),
                "overall": float(overall),
            }
        }

        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        feedback.push_info(f"质量评分: {overall:.1f}/100")

        result = AlgoResult(
            status=0,
            message=f"模型质量评定完成, 评分 {overall:.1f}/100",
            outputs=[output_report],
            metadata=report
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
