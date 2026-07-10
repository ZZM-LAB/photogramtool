"""A22 拓扑关系自动构建

构建矢量要素间的拓扑关系:
    1. 读取矢量GeoJSON
    2. 检测多边形相邻关系
    3. 构建拓扑邻接图
    4. 检测拓扑错误(重叠/缝隙)
    5. 输出拓扑关系网络
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A22TopologyBuilder(Algorithm):
    """A22 拓扑关系自动构建"""

    @staticmethod
    def name() -> str:
        return "a22_topology_builder"

    @staticmethod
    def display_name() -> str:
        return "A22 拓扑关系自动构建"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "构建多边形相邻拓扑关系,检测重叠/缝隙"

    @staticmethod
    def can_execute() -> bool:
        try:
            from shapely.geometry import shape
            from shapely.ops import unary_union
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: GeoJSON路径 (str)
        """
        geojson_path = input_data
        if not geojson_path or not os.path.exists(geojson_path):
            return AlgoResult(status=1, message=f"GeoJSON无效: {geojson_path}")

        output_path = context.param("output_path",
                                     geojson_path.replace(".geojson", "_topology.json"))

        feedback.push_info(f"输入: {geojson_path}")

        from shapely.geometry import shape as shp_shape
        from shapely.ops import unary_union

        # 1. 读取
        feedback.set_progress_text("读取矢量数据...")
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        features = geojson["features"]
        n = len(features)
        feedback.push_info(f"要素数: {n}")
        feedback.set_progress(20)

        if n < 2:
            return AlgoResult(status=1, message="要素数不足")

        # 2. 构建几何列表
        geometries = []
        for feat in features:
            geom = shp_shape(feat["geometry"])
            if not geom.is_valid:
                geom = geom.buffer(0)
            geometries.append(geom)
        feedback.set_progress(40)

        # 3. 检测相邻关系
        feedback.set_progress_text("构建拓扑邻接关系...")
        adjacency = []
        overlaps = []

        for i in range(n):
            for j in range(i + 1, n):
                gi, gj = geometries[i], geometries[j]

                # 相邻(共享边界)
                if gi.touches(gj):
                    shared = gi.intersection(gj)
                    length = shared.length if hasattr(shared, 'length') else 0
                    adjacency.append({
                        "feature1": i,
                        "feature2": j,
                        "shared_length": float(length)
                    })

                # 重叠(拓扑错误)
                if gi.overlaps(gj):
                    overlap_area = gi.intersection(gj).area
                    overlaps.append({
                        "feature1": i,
                        "feature2": j,
                        "overlap_area": float(overlap_area)
                    })

            if i % max(1, n // 10) == 0:
                feedback.set_progress(40 + int(i / n * 50))

        feedback.set_progress(70)

        # 4. 检测缝隙
        feedback.set_progress_text("检测缝隙...")
        union = unary_union(geometries)
        gaps = []
        if hasattr(union, 'interiors'):
            for interior in union.interiors:
                from shapely.geometry import Polygon
                gap = Polygon(interior)
                if gap.area > 1.0:  # 大于1平方米的缝隙
                    gaps.append({
                        "area": float(gap.area)
                    })

        feedback.set_progress(90)

        # 5. 输出
        result = {
            "feature_count": n,
            "adjacency_count": len(adjacency),
            "overlap_count": len(overlaps),
            "gap_count": len(gaps),
            "adjacency": adjacency[:100],  # 限制输出
            "overlaps": overlaps,
            "gaps": gaps,
            "summary": {
                "total_shared_length": sum(a["shared_length"] for a in adjacency),
                "total_overlap_area": sum(o["overlap_area"] for o in overlaps),
                "total_gap_area": sum(g["area"] for g in gaps),
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        feedback.push_info(f"相邻关系: {len(adjacency)}")
        feedback.push_info(f"重叠错误: {len(overlaps)}")
        feedback.push_info(f"缝隙: {len(gaps)}")

        return AlgoResult(
            status=0,
            message=f"拓扑构建完成: {len(adjacency)} 相邻, {len(overlaps)} 重叠, {len(gaps)} 缝隙",
            outputs=[output_path],
            metadata=result["summary"]
        )
