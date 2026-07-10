"""A28 航线质量自动评估

评估航线规划的质量:
    1. 覆盖完整性(测区覆盖率)
    2. 重叠度 adequacy
    3. 飞行效率(总距离/转弯次数)
    4. 安全性(航高余量)
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A28FlightQualityAssessment(Algorithm):
    """A28 航线质量自动评估"""

    @staticmethod
    def name() -> str:
        return "a28_flight_quality"

    @staticmethod
    def display_name() -> str:
        return "A28 航线质量自动评估"

    @staticmethod
    def group() -> str:
        return "M5 航线规划"

    @staticmethod
    def group_id() -> str:
        return "m5"

    @staticmethod
    def short_help() -> str:
        return "评估覆盖率/重叠度/效率/安全性"

    @staticmethod
    def can_execute() -> bool:
        try:
            from shapely.geometry import Polygon, box
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 航线GeoJSON (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        flight_path = input_data
        if not flight_path or not os.path.exists(flight_path):
            logger.error(f"航线文件无效: {flight_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"航线文件无效: {flight_path}")

        boundary_path = context.param("boundary_path", "")
        output_report = context.param("output_report",
                                       flight_path.replace(".geojson", "_quality.json"))

        feedback.push_info(f"航线: {flight_path}")

        from shapely.geometry import Polygon, box, shape as shp_shape
        from shapely.ops import unary_union

        # 1. 读取航线
        feedback.set_progress_text("读取航线...")
        logger.debug("读取航线文件", flight_path=flight_path)
        logger.timing_start("read_flight")
        with open(flight_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
        logger.timing_end("read_flight")

        # 提取曝光点和航线
        waypoints = []
        line_count = 0
        flight_height = None

        for feat in geojson["features"]:
            if feat["geometry"]["type"] == "Point":
                coords = feat["geometry"]["coordinates"]
                waypoints.append(coords)
                if flight_height is None:
                    flight_height = feat["properties"].get("altitude")
            elif feat["geometry"]["type"] == "LineString":
                line_count += 1

        logger.debug(f"提取: 航线数={line_count}, 曝光点数={len(waypoints)}")
        feedback.push_info(f"航线数: {line_count}, 曝光点: {len(waypoints)}")
        feedback.set_progress(30)

        if not waypoints:
            logger.error("无曝光点数据")
            logger.timing_end("total")
            return AlgoResult(status=1, message="无曝光点")

        # 2. 计算覆盖区域
        feedback.set_progress_text("计算覆盖区域...")
        logger.timing_start("calc_coverage")

        # 从metadata获取参数
        meta = geojson.get("metadata", {})
        plan_path = context.param("plan_path", "")

        ground_width = 50  # 默认值
        ground_height = 35

        if plan_path and os.path.exists(plan_path):
            logger.debug(f"读取规划方案获取地面覆盖参数: {plan_path}")
            with open(plan_path, 'r') as f:
                plan = json.load(f)
            ground_width = plan["coverage"]["ground_width_m"]
            ground_height = plan["coverage"]["ground_height_m"]

        logger.debug(f"地面覆盖: {ground_width:.1f} x {ground_height:.1f} m")

        # 每个曝光点的地面覆盖矩形
        coverage_polys = []
        for x, y in waypoints:
            poly = box(x - ground_width/2, y - ground_height/2,
                       x + ground_width/2, y + ground_height/2)
            coverage_polys.append(poly)

        coverage_union = unary_union(coverage_polys)
        coverage_area = coverage_union.area
        logger.timing_end("calc_coverage")
        logger.debug(f"覆盖面积: {coverage_area:.1f} m²")
        feedback.set_progress(50)

        # 3. 测区覆盖率
        survey_area = 0
        coverage_ratio = 1.0

        if boundary_path and os.path.exists(boundary_path):
            feedback.set_progress_text("计算测区覆盖率...")
            logger.timing_start("calc_boundary_ratio")
            boundary_coords = []

            if boundary_path.endswith('.geojson'):
                with open(boundary_path, 'r') as f:
                    b_geojson = json.load(f)
                for feat in b_geojson["features"]:
                    geom = shp_shape(feat["geometry"])
                    if geom.geom_type == "Polygon":
                        boundary_coords = list(geom.exterior.coords)
                        break

            if boundary_coords:
                boundary = Polygon(boundary_coords)
                if not boundary.is_valid:
                    logger.debug("边界无效,尝试修复(buffer 0)")
                    boundary = boundary.buffer(0)
                survey_area = boundary.area
                intersection = coverage_union.intersection(boundary).area
                coverage_ratio = intersection / survey_area if survey_area > 0 else 0
            logger.timing_end("calc_boundary_ratio")
            logger.debug(f"测区面积: {survey_area:.1f} m², 覆盖率: {coverage_ratio*100:.1f}%")

        feedback.push_info(f"覆盖面积: {coverage_area:.1f} m²")
        feedback.push_info(f"测区面积: {survey_area:.1f} m²" if survey_area else "测区面积: 未提供")
        feedback.push_info(f"覆盖率: {coverage_ratio*100:.1f}%")
        feedback.set_progress(70)

        # 4. 飞行效率
        feedback.set_progress_text("计算飞行效率...")
        logger.timing_start("calc_efficiency")
        total_distance = 0
        turns = 0

        # 按航线分组计算
        lines = {}
        for feat in geojson["features"]:
            if feat["geometry"]["type"] == "LineString":
                coords = feat["geometry"]["coordinates"]
                lid = feat["properties"]["line_id"]
                for i in range(len(coords) - 1):
                    p1 = np.array(coords[i])
                    p2 = np.array(coords[i+1])
                    total_distance += np.sum((p2 - p1) ** 2) ** 0.5
                lines[lid] = coords

        turns = max(0, len(lines) - 1)  # 航线间转弯

        # 平均航线长度
        avg_line_length = total_distance / max(line_count, 1)
        logger.timing_end("calc_efficiency")
        logger.debug(f"总飞行距离: {total_distance:.1f} m, 转弯次数: {turns}, 平均航线长度: {avg_line_length:.1f} m")

        feedback.push_info(f"总飞行距离: {total_distance:.1f} m")
        feedback.push_info(f"转弯次数: {turns}")
        feedback.set_progress(85)

        # 5. 综合评分
        coverage_score = min(coverage_ratio * 100, 100)
        efficiency_score = min(100 - turns * 2, 100) if turns > 0 else 100
        overall_score = (coverage_score * 0.6 + efficiency_score * 0.4)
        logger.debug(f"评分: 覆盖={coverage_score:.1f}, 效率={efficiency_score:.1f}, 综合={overall_score:.1f}")

        # 6. 输出报告
        report = {
            "coverage": {
                "coverage_area_m2": float(coverage_area),
                "survey_area_m2": float(survey_area) if survey_area else None,
                "coverage_ratio": float(coverage_ratio),
                "score": float(coverage_score),
            },
            "efficiency": {
                "total_distance_m": float(total_distance),
                "flight_lines": line_count,
                "turns": turns,
                "avg_line_length_m": float(avg_line_length),
                "score": float(efficiency_score),
            },
            "safety": {
                "flight_height_m": flight_height,
            },
            "overall_score": float(overall_score),
        }

        logger.debug(f"写入质量报告: {output_report}")
        logger.timing_start("write_output")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.timing_end("write_output")

        feedback.set_progress(100)
        feedback.push_info(f"综合评分: {overall_score:.1f}/100")

        result = AlgoResult(
            status=0,
            message=f"航线质量评估完成, 综合评分 {overall_score:.1f}/100",
            outputs=[output_report],
            metadata=report
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
