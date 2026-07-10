"""A26 航线自动生成

根据航摄规划方案生成具体航线和曝光点:
    1. 读取规划方案
    2. 生成航线起止点
    3. 沿航线生成曝光点坐标
    4. 输出航线GeoJSON
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A26FlightLineGeneration(Algorithm):
    """A26 航线自动生成"""

    @staticmethod
    def name() -> str:
        return "a26_flight_line_generation"

    @staticmethod
    def display_name() -> str:
        return "A26 航线自动生成"

    @staticmethod
    def group() -> str:
        return "M5 航线规划"

    @staticmethod
    def group_id() -> str:
        return "m5"

    @staticmethod
    def short_help() -> str:
        return "根据规划方案生成航线和曝光点"

    @staticmethod
    def can_execute() -> bool:
        return True

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 规划方案JSON (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        plan_path = input_data
        if not plan_path or not os.path.exists(plan_path):
            logger.error(f"规划文件无效: {plan_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"规划文件无效: {plan_path}")

        output_geojson = context.param("output_geojson",
                                        plan_path.replace("_plan.json", "_flightlines.geojson"))

        # 1. 读取规划
        feedback.set_progress_text("读取规划方案...")
        logger.debug("读取规划方案", plan_path=plan_path)
        logger.timing_start("read_plan")
        with open(plan_path, 'r', encoding='utf-8') as f:
            plan = json.load(f)
        logger.timing_end("read_plan")
        feedback.set_progress(20)

        bounds = plan["survey_area"]["bounds"]
        coverage = plan["coverage"]
        estimate = plan["estimate"]
        flight_height = plan["flight_params"]["flight_height_m"]

        minx, miny, maxx, maxy = bounds
        line_spacing = coverage["line_spacing_m"]
        exposure_spacing = coverage["exposure_spacing_m"]
        n_lines = estimate["flight_lines"]
        n_photos = estimate["photos_per_line"]
        logger.debug(f"规划参数: n_lines={n_lines}, n_photos={n_photos}, line_spacing={line_spacing:.1f}, exposure_spacing={exposure_spacing:.1f}")

        # 2. 生成航线
        feedback.set_progress_text("生成航线和曝光点...")
        logger.timing_start("gen_lines")
        features = []

        for line_idx in range(n_lines):
            # 航线Y坐标(从北到南)
            y = maxy - (line_idx + 0.5) * line_spacing

            # 之字形飞行: 偶数航线从西向东,奇数航线从东向西
            if line_idx % 2 == 0:
                x_start, x_end, step = minx, maxx, exposure_spacing
            else:
                x_start, x_end, step = maxx, minx, -exposure_spacing

            # 生成曝光点
            waypoints = []
            n_pts = n_photos
            for i in range(n_pts):
                x = x_start + i * step
                waypoints.append([float(x), float(y)])

            if len(waypoints) < 2:
                continue

            # 航线
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": waypoints
                },
                "properties": {
                    "line_id": line_idx + 1,
                    "direction": "E" if line_idx % 2 == 0 else "W",
                    "photo_count": len(waypoints),
                    "altitude": flight_height,
                }
            })

            # 曝光点
            for i, wp in enumerate(waypoints):
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": wp
                    },
                    "properties": {
                        "line_id": line_idx + 1,
                        "photo_id": i + 1,
                        "altitude": flight_height,
                    }
                })

            feedback.set_progress(20 + int((line_idx + 1) / n_lines * 70))

        # 3. 输出
        feedback.set_progress_text("保存航线...")
        logger.timing_end("gen_lines")
        logger.debug(f"生成要素数: {len(features)}")
        geojson = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "flight_lines": n_lines,
                "total_photos": n_lines * n_photos,
                "flight_height": flight_height,
            }
        }
        logger.debug(f"写入航线GeoJSON: {output_geojson}")
        logger.timing_start("write_output")
        with open(output_geojson, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False)
        logger.timing_end("write_output")

        feedback.set_progress(100)
        feedback.push_info(f"航线生成: {n_lines}条, {len(features)}个要素")

        result = AlgoResult(
            status=0,
            message=f"航线生成完成: {n_lines}条航线, {n_lines * n_photos}个曝光点",
            outputs=[output_geojson],
            metadata={
                "output_geojson": output_geojson,
                "flight_lines": n_lines,
                "total_photos": n_lines * n_photos,
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
