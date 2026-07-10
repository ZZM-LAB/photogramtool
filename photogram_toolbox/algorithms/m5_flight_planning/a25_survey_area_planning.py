"""A25 测区自动识别与覆盖规划

根据输入的测区边界(矢量/坐标)自动规划航摄参数:
    1. 解析测区边界
    2. 计算测区面积/形状
    3. 根据GSD确定航高
    4. 计算所需航线数和照片数
    5. 输出航摄规划方案
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A25SurveyAreaPlanning(Algorithm):
    """A25 测区自动识别与覆盖规划"""

    @staticmethod
    def name() -> str:
        return "a25_survey_area_planning"

    @staticmethod
    def display_name() -> str:
        return "A25 测区自动识别与覆盖规划"

    @staticmethod
    def group() -> str:
        return "M5 航线规划"

    @staticmethod
    def group_id() -> str:
        return "m5"

    @staticmethod
    def short_help() -> str:
        return "解析测区边界,计算航高/航线数/照片数"

    @staticmethod
    def can_execute() -> bool:
        try:
            from shapely.geometry import Polygon
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 测区边界文件 (str, GeoJSON/坐标txt)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        boundary_path = input_data
        if not boundary_path or not os.path.exists(boundary_path):
            logger.error(f"边界文件无效: {boundary_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"边界文件无效: {boundary_path}")

        # 航摄参数
        gsd = context.param("gsd", 0.05)  # 地面采样距离(米)
        overlap = context.param("overlap", 80)  # 航向重叠度(%)
        sidelap = context.param("sidelap", 60)  # 旁向重叠度(%)
        focal_length = context.param("focal_length", 24)  # 焦距(mm)
        image_width = context.param("image_width", 5472)  # 像素
        image_height = context.param("image_height", 3648)
        pixel_size = context.param("pixel_size", 2.41)  # 像元大小(μm)

        feedback.push_info(f"GSD: {gsd}m, 航向重叠: {overlap}%, 旁向重叠: {sidelap}%")

        from shapely.geometry import Polygon, shape as shp_shape
        from shapely.ops import unary_union

        # 1. 解析边界
        feedback.set_progress_text("解析测区边界...")
        logger.debug("开始解析测区边界", boundary_path=boundary_path)
        logger.timing_start("parse_boundary")
        coords = []

        if boundary_path.endswith('.geojson') or boundary_path.endswith('.json'):
            with open(boundary_path, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
            for feat in geojson["features"]:
                geom = shp_shape(feat["geometry"])
                if geom.geom_type == "Polygon":
                    coords.extend(list(geom.exterior.coords))
                elif geom.geom_type == "MultiPolygon":
                    for poly in geom.geoms:
                        coords.extend(list(poly.exterior.coords))
        else:
            # 坐标文件: x y 每行
            with open(boundary_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        coords.append([float(parts[0]), float(parts[1])])

        logger.timing_end("parse_boundary")
        logger.debug(f"解析得到边界点数: {len(coords)}")

        if len(coords) < 3:
            logger.error(f"边界点数不足(需≥3), 实际: {len(coords)}")
            logger.timing_end("total")
            return AlgoResult(status=1, message="边界点数不足(需≥3)")

        boundary = Polygon(coords)
        if not boundary.is_valid:
            logger.debug("边界无效,尝试修复(buffer 0)")
            boundary = boundary.buffer(0)
        feedback.set_progress(30)

        # 2. 测区信息
        logger.timing_start("calc_area")
        area = boundary.area
        bounds = boundary.bounds  # (minx, miny, maxx, maxy)
        width_m = bounds[2] - bounds[0]
        height_m = bounds[3] - bounds[1]
        logger.timing_end("calc_area")
        logger.debug(f"测区面积: {area:.1f} m², 范围: {width_m:.1f} x {height_m:.1f} m")

        feedback.push_info(f"测区面积: {area:.1f} m² ({area/1e6:.4f} km²)")
        feedback.push_info(f"测区范围: {width_m:.1f} x {height_m:.1f} m")

        # 3. 航高计算
        # H = GSD * f / pixel_size
        # f: 焦距(mm), pixel_size: 像元(μm), GSD: 米
        logger.timing_start("calc_height")
        flight_height = gsd * focal_length / (pixel_size / 1000)
        logger.timing_end("calc_height")
        logger.debug(f"航高: {flight_height:.1f} m", gsd=gsd, focal_length=focal_length)
        feedback.push_info(f"航高: {flight_height:.1f} m")
        feedback.set_progress(50)

        # 4. 航线数和照片数
        # 地面覆盖范围
        logger.timing_start("calc_coverage")
        ground_width = image_width * gsd  # 单张影像地面宽度
        ground_height = image_height * gsd  # 单张影像地面高度

        # 航线间距(考虑旁向重叠)
        line_spacing = ground_width * (1 - sidelap / 100)
        # 曝光间距(考虑航向重叠)
        exposure_spacing = ground_height * (1 - overlap / 100)

        # 航线数
        n_lines = int(np.ceil(height_m / line_spacing))
        # 每条航线的照片数
        n_photos_per_line = int(np.ceil(width_m / exposure_spacing))
        total_photos = n_lines * n_photos_per_line
        logger.timing_end("calc_coverage")
        logger.debug(f"航线数: {n_lines}, 每线照片: {n_photos_per_line}, 总照片: {total_photos}")

        feedback.push_info(f"地面覆盖: {ground_width:.1f} x {ground_height:.1f} m")
        feedback.push_info(f"航线间距: {line_spacing:.1f} m, 曝光间距: {exposure_spacing:.1f} m")
        feedback.push_info(f"航线数: {n_lines}, 每线照片: {n_photos_per_line}, 总照片: {total_photos}")
        feedback.set_progress(80)

        # 5. 输出方案
        plan = {
            "survey_area": {
                "area_m2": float(area),
                "bounds": [float(b) for b in bounds],
                "width_m": float(width_m),
                "height_m": float(height_m),
            },
            "camera": {
                "focal_length_mm": focal_length,
                "image_width_px": image_width,
                "image_height_px": image_height,
                "pixel_size_um": pixel_size,
            },
            "flight_params": {
                "gsd_m": gsd,
                "flight_height_m": float(flight_height),
                "overlap_percent": overlap,
                "sidelap_percent": sidelap,
            },
            "coverage": {
                "ground_width_m": float(ground_width),
                "ground_height_m": float(ground_height),
                "line_spacing_m": float(line_spacing),
                "exposure_spacing_m": float(exposure_spacing),
            },
            "estimate": {
                "flight_lines": n_lines,
                "photos_per_line": n_photos_per_line,
                "total_photos": total_photos,
            }
        }

        output_path = context.param("output_path",
                                     boundary_path.rsplit('.', 1)[0] + "_plan.json")
        logger.debug(f"写入规划方案到: {output_path}")
        logger.timing_start("write_output")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        logger.timing_end("write_output")

        feedback.set_progress(100)
        feedback.push_info(f"规划方案: {output_path}")

        result = AlgoResult(
            status=0,
            message=f"测区规划完成: {n_lines}航线, {total_photos}照片, 航高{flight_height:.0f}m",
            outputs=[output_path],
            metadata=plan
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
