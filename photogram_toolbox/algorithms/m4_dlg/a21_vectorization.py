"""A21 矢量化提取

将分割结果栅格转为矢量多边形:
    1. 读取分割图
    2. 栅格转矢量(rasterio.features.shapes)
    3. 过滤小面积区域
    4. 简化几何(shapely)
    5. 输出GeoJSON
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A21Vectorization(Algorithm):
    """A21 矢量化提取"""

    @staticmethod
    def name() -> str:
        return "a21_vectorization"

    @staticmethod
    def display_name() -> str:
        return "A21 矢量化提取"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "分割栅格转矢量多边形,过滤+简化"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            from shapely.geometry import shape
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 分割图路径 (str, .tif)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")
        seg_path = input_data
        if not seg_path or not os.path.exists(seg_path):
            logger.error(f"分割图无效: {seg_path}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status=1")
            return AlgoResult(status=1, message=f"分割图无效: {seg_path}")

        output_geojson = context.param("output_geojson",
                                        seg_path.replace(".tif", "_vectors.geojson"))
        min_area = context.param("min_area", 100.0)  # 最小面积(平方米)
        simplify_tolerance = context.param("simplify_tolerance", 1.0)

        feedback.push_info(f"输入: {seg_path}")

        import rasterio
        from rasterio.features import shapes
        from shapely.geometry import shape as shp_shape, mapping
        from shapely.ops import unary_union
        import json

        # 1. 读取分割图
        logger.debug("开始读取分割图")
        logger.timing_start("read_seg")
        feedback.set_progress_text("读取分割图...")
        with rasterio.open(seg_path) as src:
            seg = src.read(1)
            transform = src.transform
            crs = src.crs
        feedback.push_info(f"分割图尺寸: {seg.shape}")
        feedback.set_progress(20)
        logger.timing_end("read_seg")
        logger.debug(f"分割图读取完成, 尺寸={seg.shape}")

        # 2. 栅格转矢量
        logger.debug("开始栅格转矢量")
        logger.timing_start("raster_to_vector")
        feedback.set_progress_text("栅格转矢量...")
        features = []
        class_stats = {}

        for geom, value in shapes(seg, transform=transform):
            poly = shp_shape(geom)
            if not poly.is_valid:
                poly = poly.buffer(0)

            area = poly.area
            if area < min_area:
                continue

            # 简化
            if simplify_tolerance > 0:
                poly = poly.simplify(simplify_tolerance, preserve_topology=True)

            if poly.is_empty:
                continue

            class_id = int(value)
            if class_id not in class_stats:
                class_stats[class_id] = {"count": 0, "area": 0}
            class_stats[class_id]["count"] += 1
            class_stats[class_id]["area"] += area

            features.append({
                "type": "Feature",
                "geometry": mapping(poly),
                "properties": {
                    "class_id": class_id,
                    "area": area,
                }
            })

        feedback.set_progress(70)
        feedback.push_info(f"提取多边形: {len(features)} 个")
        logger.timing_end("raster_to_vector")
        logger.debug(f"栅格转矢量完成, 多边形数={len(features)}")

        # 3. 输出
        logger.debug("开始保存GeoJSON")
        logger.timing_start("save")
        feedback.set_progress_text("保存GeoJSON...")
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "crs": str(crs) if crs else "unknown",
                "class_stats": {str(k): v for k, v in class_stats.items()},
            }
        }
        with open(output_geojson, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)
        logger.timing_end("save")
        logger.debug(f"GeoJSON已保存: {output_geojson}")

        feedback.set_progress(100)
        for cid, stats in class_stats.items():
            feedback.push_info(f"  类别 {cid}: {stats['count']} 个多边形, 总面积 {stats['area']:.1f}m²")

        result = AlgoResult(
            status=0,
            message=f"矢量化完成, {len(features)} 个多边形",
            outputs=[output_geojson],
            metadata={
                "output_geojson": output_geojson,
                "feature_count": len(features),
                "class_stats": class_stats,
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
