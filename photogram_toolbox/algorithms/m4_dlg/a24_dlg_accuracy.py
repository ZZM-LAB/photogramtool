"""A24 DLG精度自动评定

评估DLG提取的精度:
    1. 与参考矢量数据对比
    2. 计算交并比(IoU)
    3. 计算精度/召回率/F1
    4. 输出混淆矩阵
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A24DLGAccuracy(Algorithm):
    """A24 DLG精度自动评定"""

    @staticmethod
    def name() -> str:
        return "a24_dlg_accuracy"

    @staticmethod
    def display_name() -> str:
        return "A24 DLG精度自动评定"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "与参考数据对比,计算IoU/F1/混淆矩阵"

    @staticmethod
    def can_execute() -> bool:
        try:
            from shapely.geometry import shape
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 待评估的分割图路径 (str, .tif)
        """
        seg_path = input_data
        if not seg_path or not os.path.exists(seg_path):
            return AlgoResult(status=1, message=f"分割图无效: {seg_path}")

        ref_path = context.param("ref_path", "")
        output_report = context.param("output_report",
                                       seg_path.replace(".tif", "_accuracy.json"))

        feedback.push_info(f"分割图: {seg_path}")
        feedback.push_info(f"参考数据: {ref_path}")

        import rasterio
        from shapely.geometry import shape as shp_shape

        # 1. 读取分割结果
        feedback.set_progress_text("读取分割结果...")
        with rasterio.open(seg_path) as src:
            seg = src.read(1)
        feedback.push_info(f"分割图尺寸: {seg.shape}")
        feedback.set_progress(30)

        classes = np.unique(seg)
        classes = classes[classes >= 0]
        n_classes = len(classes)

        # 2. 如果有参考数据,计算指标
        if ref_path and os.path.exists(ref_path):
            feedback.set_progress_text("读取参考数据...")

            if ref_path.endswith('.tif'):
                with rasterio.open(ref_path) as src:
                    ref = src.read(1)
            elif ref_path.endswith('.geojson'):
                # 栅格化GeoJSON
                from rasterio.features import rasterize
                with open(ref_path, 'r') as f:
                    geojson = json.load(f)

                with rasterio.open(seg_path) as src:
                    transform = src.transform
                    shape = src.shape

                geometries = [(shp_shape(feat["geometry"]),
                               feat["properties"].get("class_id", 1))
                              for feat in geojson["features"]]
                ref = rasterize(
                    geometries,
                    out_shape=shape,
                    transform=transform,
                    fill=0
                ).astype(np.uint8)
            else:
                return AlgoResult(status=1, message=f"不支持的参考格式: {ref_path}")

            feedback.set_progress(50)

            if ref.shape != seg.shape:
                return AlgoResult(status=1, message="分割图与参考图尺寸不匹配")

            # 3. 计算混淆矩阵
            feedback.set_progress_text("计算精度指标...")
            conf_matrix = np.zeros((n_classes, n_classes), dtype=int)
            for i, ci in enumerate(classes):
                for j, cj in enumerate(classes):
                    conf_matrix[i, j] = np.sum((seg == ci) & (ref == cj))

            # 计算每类指标
            metrics = {}
            for i, c in enumerate(classes):
                tp = conf_matrix[i, i]
                fp = conf_matrix[:, i].sum() - tp
                fn = conf_matrix[i, :].sum() - tp

                precision = tp / (tp + fp) if (tp + fp) > 0 else 0
                recall = tp / (tp + fn) if (tp + fn) > 0 else 0
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                iou = tp / (tp + fp + fn) if (tp + fp + fn) > 0 else 0

                metrics[int(c)] = {
                    "precision": float(precision),
                    "recall": float(recall),
                    "f1": float(f1),
                    "iou": float(iou),
                }

            # 总体精度
            oa = np.trace(conf_matrix) / np.sum(conf_matrix) if np.sum(conf_matrix) > 0 else 0
            # 平均IoU
            mean_iou = np.mean([m["iou"] for m in metrics.values()])

            feedback.set_progress(80)

            result = {
                "overall_accuracy": float(oa),
                "mean_iou": float(mean_iou),
                "confusion_matrix": conf_matrix.tolist(),
                "classes": [int(c) for c in classes],
                "per_class": metrics,
            }
        else:
            # 无参考数据,输出统计信息
            feedback.push_warning("未提供参考数据,仅输出统计信息")
            feedback.set_progress(60)

            stats = {}
            for c in classes:
                count = np.sum(seg == c)
                stats[int(c)] = {
                    "pixel_count": int(count),
                    "percentage": float(count / seg.size * 100)
                }

            result = {
                "overall_accuracy": None,
                "mean_iou": None,
                "classes": [int(c) for c in classes],
                "class_statistics": stats,
                "note": "无参考数据,未计算精度指标"
            }

        # 4. 输出报告
        feedback.set_progress_text("生成报告...")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        if result.get("mean_iou") is not None:
            feedback.push_info(f"总体精度: {result['overall_accuracy']:.4f}")
            feedback.push_info(f"平均IoU: {result['mean_iou']:.4f}")
            for c, m in result["per_class"].items():
                feedback.push_info(f"  类别{c}: IoU={m['iou']:.4f}, F1={m['f1']:.4f}")

        return AlgoResult(
            status=0,
            message=f"精度评定完成" + (f", mIoU={result['mean_iou']:.4f}"
                                      if result.get("mean_iou") else ""),
            outputs=[output_report],
            metadata=result
        )
