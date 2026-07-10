"""A23 DLG自动符号化

按制图标准对DLG要素进行符号化渲染:
    1. 读取矢量GeoJSON
    2. 按类别分配符号(颜色/线型/填充)
    3. 渲染为PNG/PDF地图
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A23DLGSymbolization(Algorithm):
    """A23 DLG自动符号化"""

    @staticmethod
    def name() -> str:
        return "a23_dlg_symbolization"

    @staticmethod
    def display_name() -> str:
        return "A23 DLG自动符号化"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "按制图标准渲染DLG要素为地图"

    @staticmethod
    def can_execute() -> bool:
        try:
            import matplotlib
            from shapely.geometry import shape
            return True
        except ImportError:
            return False

    # DLG标准符号表
    SYMBOL_TABLE = {
        0: {"name": "背景", "color": "#FFFFFF", "linestyle": "none"},
        1: {"name": "建筑物", "color": "#FF6B6B", "fill": True, "linewidth": 1.5},
        2: {"name": "道路", "color": "#333333", "linestyle": "-", "linewidth": 2.0},
        3: {"name": "植被", "color": "#51CF66", "fill": True, "linewidth": 0.5},
        4: {"name": "水体", "color": "#339AF0", "fill": True, "linewidth": 0.5},
        5: {"name": "裸地", "color": "#FFD43B", "fill": True, "linewidth": 0.5},
    }

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: GeoJSON路径 (str)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")
        geojson_path = input_data
        if not geojson_path or not os.path.exists(geojson_path):
            logger.error(f"GeoJSON无效: {geojson_path}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status=1")
            return AlgoResult(status=1, message=f"GeoJSON无效: {geojson_path}")

        output_png = context.param("output_png",
                                    geojson_path.replace(".geojson", "_map.png"))
        dpi = context.param("dpi", 300)

        feedback.push_info(f"输入: {geojson_path}")

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Polygon as MplPolygon
        from matplotlib.collections import PatchCollection
        from shapely.geometry import shape as shp_shape

        # 1. 读取
        logger.debug("开始读取矢量数据")
        logger.timing_start("read")
        feedback.set_progress_text("读取矢量数据...")
        with open(geojson_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        features = geojson["features"]
        feedback.push_info(f"要素数: {len(features)}")
        feedback.set_progress(20)
        logger.timing_end("read")
        logger.debug(f"矢量数据读取完成, 要素数={len(features)}")

        # 2. 按类别分组
        logger.debug("开始符号化渲染")
        logger.timing_start("render")
        feedback.set_progress_text("符号化渲染...")
        fig, ax = plt.subplots(1, 1, figsize=(12, 12))

        class_patches = {}
        for feat in features:
            class_id = feat["properties"].get("class_id", 0)
            geom = shp_shape(feat["geometry"])

            symbol = self.SYMBOL_TABLE.get(class_id, self.SYMBOL_TABLE[0])
            color = symbol.get("color", "#888888")

            if geom.geom_type == "Polygon":
                x, y = geom.exterior.xy
                ax.fill(x, y, color=color, alpha=0.7 if symbol.get("fill") else 0,
                        edgecolor=color, linewidth=symbol.get("linewidth", 1),
                        linestyle=symbol.get("linestyle", "-"))
            elif geom.geom_type == "MultiPolygon":
                for poly in geom.geoms:
                    x, y = poly.exterior.xy
                    ax.fill(x, y, color=color, alpha=0.7 if symbol.get("fill") else 0,
                            edgecolor=color, linewidth=symbol.get("linewidth", 1),
                            linestyle=symbol.get("linestyle", "-"))

        feedback.set_progress(60)
        logger.timing_end("render")
        logger.debug("符号化渲染完成")

        # 3. 图例
        legend_handles = []
        from matplotlib.patches import Patch
        for cid, symbol in self.SYMBOL_TABLE.items():
            if cid == 0:
                continue
            legend_handles.append(
                Patch(facecolor=symbol["color"], label=symbol["name"])
            )
        ax.legend(handles=legend_handles, loc='upper right', fontsize=10)

        ax.set_aspect('equal')
        ax.set_title("DLG Symbolization Map", fontsize=16)
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.grid(True, alpha=0.3)

        feedback.set_progress(80)

        # 4. 保存
        logger.debug("开始保存地图")
        logger.timing_start("save")
        feedback.set_progress_text("保存地图...")
        plt.tight_layout()
        plt.savefig(output_png, dpi=dpi, bbox_inches='tight')
        plt.close()
        logger.timing_end("save")
        logger.debug(f"地图已保存: {output_png}")

        feedback.set_progress(100)
        feedback.push_info(f"地图保存: {output_png}")

        result = AlgoResult(
            status=0,
            message=f"DLG符号化完成",
            outputs=[output_png],
            metadata={
                "output_png": output_png,
                "feature_count": len(features),
                "dpi": dpi,
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
