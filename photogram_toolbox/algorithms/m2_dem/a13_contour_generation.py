"""A13 DEM等高线自动生成

从DEM生成等高线:
    1. 读取DEM
    2. 按指定间距生成等高线
    3. 输出为GeoJSON或Shapefile
    4. 可选叠加DEM渲染
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A13ContourGeneration(Algorithm):
    """A13 DEM等高线自动生成"""

    @staticmethod
    def name() -> str:
        return "a13_contour_generation"

    @staticmethod
    def display_name() -> str:
        return "A13 DEM等高线自动生成"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "从DEM生成等高线,输出GeoJSON"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            import matplotlib
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: DEM路径 (str, .tif)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        dem_path = input_data
        if not dem_path or not os.path.exists(dem_path):
            logger.error(f"DEM文件无效: {dem_path}")
            result = AlgoResult(status=1, message=f"DEM文件无效: {dem_path}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        output_geojson = context.param("output_geojson",
                                        dem_path.replace(".tif", "_contours.geojson"))
        interval = context.param("interval", 5.0)  # 等高距(米)

        feedback.push_info(f"DEM: {dem_path}")
        feedback.push_info(f"等高距: {interval}m")
        logger.debug(f"参数: interval={interval}, output_geojson={output_geojson}")

        import rasterio
        import matplotlib.pyplot as plt
        import json

        # 1. 读取DEM
        feedback.set_progress_text("读取DEM...")
        logger.timing_start("read_dem")
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            transform = src.transform
        logger.timing_end("read_dem")
        logger.debug(f"DEM尺寸: {dem.shape}")
        feedback.set_progress(30)

        valid = ~np.isnan(dem)
        if not np.any(valid):
            logger.error("DEM全为空")
            result = AlgoResult(status=1, message="DEM全为空")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        zmin = np.nanmin(dem)
        zmax = np.nanmax(dem)
        levels = np.arange(np.floor(zmin / interval) * interval,
                          np.ceil(zmax / interval) * interval + interval,
                          interval)
        feedback.push_info(f"高程范围: {zmin:.2f} - {zmax:.2f}m, 等高线数: {len(levels)}")
        logger.debug(f"高程范围: {zmin:.2f} - {zmax:.2f}m, 等高线数: {len(levels)}")
        feedback.set_progress(50)

        # 2. 生成等高线
        feedback.set_progress_text("生成等高线...")
        logger.timing_start("generate_contours")
        rows, cols = dem.shape
        x = np.arange(cols) * transform.a + transform.c
        y = np.arange(rows) * transform.e + transform.f

        contours = plt.contour(x, y, dem, levels=levels)
        logger.timing_end("generate_contours")
        feedback.set_progress(70)

        # 3. 转为GeoJSON
        feedback.set_progress_text("输出GeoJSON...")
        logger.timing_start("export_geojson")
        features = []
        for i, level in enumerate(contours.levels):
            try:
                paths = contours.collections[i].get_paths()
                for path in paths:
                    verts = path.vertices
                    if len(verts) < 2:
                        continue
                    coords = [[float(v[0]), float(v[1])] for v in verts]
                    coords.append(coords[0])  # 闭合
                    features.append({
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": coords
                        },
                        "properties": {
                            "elevation": float(level)
                        }
                    })
            except (IndexError, AttributeError):
                continue

        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        with open(output_geojson, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)

        plt.close()
        logger.timing_end("export_geojson")

        feedback.set_progress(100)
        feedback.push_info(f"等高线生成完成: {output_geojson} ({len(features)} 条)")
        logger.debug(f"等高线生成完成: {output_geojson}, 共 {len(features)} 条")

        result = AlgoResult(
            status=0,
            message=f"等高线生成完成, {len(features)} 条",
            outputs=[output_geojson],
            metadata={
                "output_geojson": output_geojson,
                "interval": interval,
                "zmin": float(zmin),
                "zmax": float(zmax),
                "contour_count": len(features),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
