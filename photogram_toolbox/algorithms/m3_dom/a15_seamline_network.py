"""A15 接缝线网络自动构建

基于正射影像的有效区域,用Voronoi图构建接缝线网络:
    1. 提取每张正射影像的有效区域(掩膜)
    2. 计算各影像有效区域的中心
    3. 生成Voronoi图确定每张影像的贡献区域
    4. 输出接缝线网络(GeoJSON)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A15SeamlineNetwork(Algorithm):
    """A15 接缝线网络自动构建"""

    @staticmethod
    def name() -> str:
        return "a15_seamline_network"

    @staticmethod
    def display_name() -> str:
        return "A15 接缝线网络自动构建"

    @staticmethod
    def group() -> str:
        return "M3 DOM生产"

    @staticmethod
    def group_id() -> str:
        return "m3"

    @staticmethod
    def short_help() -> str:
        return "Voronoi图构建接缝线网络,确定各影像贡献区域"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            from scipy.spatial import Voronoi
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 正射影像目录 (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        ortho_dir = input_data
        if not ortho_dir or not os.path.isdir(ortho_dir):
            logger.error(f"目录无效: {ortho_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"目录无效: {ortho_dir}")

        output_geojson = context.param("output_geojson",
                                        os.path.join(ortho_dir, "seamlines.geojson"))

        import rasterio
        from scipy.spatial import Voronoi
        import json

        # 1. 扫描正射影像
        logger.debug("开始扫描正射影像", ortho_dir=ortho_dir)
        ortho_files = [f for f in os.listdir(ortho_dir)
                       if f.endswith('_ortho.tif')]
        if not ortho_files:
            logger.error("未找到正射影像(*_ortho.tif)")
            logger.timing_end("total")
            return AlgoResult(status=1, message="未找到正射影像(*_ortho.tif)")

        feedback.push_info(f"正射影像数: {len(ortho_files)}")
        logger.debug(f"扫描到正射影像数: {len(ortho_files)}")
        feedback.set_progress(20)

        # 2. 提取各影像的有效区域中心
        centers = []
        bounds_list = []
        logger.debug("开始提取各影像有效区域中心")
        logger.timing_start("extract_centers")
        for i, fname in enumerate(ortho_files):
            fpath = os.path.join(ortho_dir, fname)
            with rasterio.open(fpath) as src:
                bounds = src.bounds
                cx = (bounds.left + bounds.right) / 2
                cy = (bounds.top + bounds.bottom) / 2
                centers.append([cx, cy])
                bounds_list.append(bounds)
            feedback.set_progress(20 + int((i + 1) / len(ortho_files) * 40))
        logger.timing_end("extract_centers")
        logger.debug(f"中心点提取完成: {len(centers)} 个")

        centers = np.array(centers)

        # 3. Voronoi 图
        feedback.set_progress_text("生成Voronoi接缝线网络...")
        if len(centers) < 2:
            logger.error("影像数不足,无法构建接缝线")
            logger.timing_end("total")
            return AlgoResult(status=1, message="影像数不足,无法构建接缝线")

        logger.debug("开始生成Voronoi图")
        logger.timing_start("voronoi")
        vor = Voronoi(centers)
        logger.timing_end("voronoi")
        logger.debug("Voronoi图生成完成")
        feedback.set_progress(70)

        # 4. 提取接缝线(Voronoi 边)
        logger.debug("开始提取接缝线(Voronoi 边)")
        logger.timing_start("extract_seamlines")
        features = []
        for i, (p1, p2) in enumerate(vor.ridge_points):
            if p1 < len(ortho_files) and p2 < len(ortho_files):
                ridge = vor.ridge_vertices[i]
                if -1 not in ridge:
                    coords = []
                    for v_idx in ridge:
                        x, y = vor.vertices[v_idx]
                        coords.append([float(x), float(y)])

                    if len(coords) >= 2:
                        features.append({
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": coords
                            },
                            "properties": {
                                "image1": ortho_files[p1],
                                "image2": ortho_files[p2],
                            }
                        })
        logger.timing_end("extract_seamlines")
        logger.debug(f"接缝线提取完成: {len(features)} 条")

        # 5. 输出
        logger.debug("开始输出GeoJSON", output_geojson=output_geojson)
        logger.timing_start("write_geojson")
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }
        with open(output_geojson, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)
        logger.timing_end("write_geojson")
        logger.debug(f"GeoJSON已写入: {output_geojson}")

        feedback.set_progress(100)
        feedback.push_info(f"接缝线生成完成: {len(features)} 条")

        result = AlgoResult(
            status=0,
            message=f"接缝线网络构建完成, {len(features)} 条",
            outputs=[output_geojson],
            metadata={
                "output_geojson": output_geojson,
                "image_count": len(ortho_files),
                "seamline_count": len(features),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
