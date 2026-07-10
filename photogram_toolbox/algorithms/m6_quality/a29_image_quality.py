"""A29 影像质量自动评定

对原始航摄影像进行质量评估:
    1. 清晰度(拉普拉斯方差)
    2. 曝光(平均亮度/直方图)
    3. 色彩(饱和度/色相分布)
    4. 输出质量报告
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A29ImageQualityAssessment(Algorithm):
    """A29 影像质量自动评定"""

    @staticmethod
    def name() -> str:
        return "a29_image_quality"

    @staticmethod
    def display_name() -> str:
        return "A29 影像质量自动评定"

    @staticmethod
    def group() -> str:
        return "M6 质量评定"

    @staticmethod
    def group_id() -> str:
        return "m6"

    @staticmethod
    def short_help() -> str:
        return "评估影像清晰度/曝光/色彩质量"

    @staticmethod
    def can_execute() -> bool:
        try:
            import cv2
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 影像目录 (str) 或单张影像路径
        """
        input_path = input_data
        if not input_path or not os.path.exists(input_path):
            return AlgoResult(status=1, message=f"路径无效: {input_path}")

        output_report = context.param("output_report",
                                       os.path.join(
                                           input_path if os.path.isdir(input_path) else os.path.dirname(input_path),
                                           "image_quality_report.json"))

        import cv2

        # 收集影像
        if os.path.isdir(input_path):
            exts = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
            image_files = [os.path.join(input_path, f)
                           for f in os.listdir(input_path)
                           if f.lower().endswith(exts)]
        else:
            image_files = [input_path]

        if not image_files:
            return AlgoResult(status=1, message="未找到影像文件")

        feedback.push_info(f"影像数: {len(image_files)}")
        feedback.set_progress(10)

        results = []
        for i, img_path in enumerate(image_files):
            if feedback.is_canceled():
                return AlgoResult(status=2, message="用户取消")

            # 读取影像
            img = cv2.imread(img_path)
            if img is None:
                # 尝试 rasterio 读取 TIFF
                try:
                    import rasterio
                    with rasterio.open(img_path) as src:
                        data = src.read()
                    img = np.transpose(data[:3], (1, 2, 0))
                    img = img[:, :, ::-1]  # RGB → BGR
                except Exception:
                    results.append({"file": os.path.basename(img_path), "error": "读取失败"})
                    continue

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape

            # 1. 清晰度(拉普拉斯方差)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = float(laplacian.var())

            # 2. 曝光(平均亮度)
            mean_brightness = float(gray.mean())
            # 直方图分布
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
            hist_norm = hist / hist.sum()
            # 欠曝/过曝比例
            under_exposed = float(hist_norm[:10].sum() * 100)
            over_exposed = float(hist_norm[-10:].sum() * 100)

            # 3. 色彩
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mean_saturation = float(hsv[:, :, 1].mean())
            mean_hue = float(hsv[:, :, 0].mean())

            # 质量评分
            # 清晰度: >100 良好, <50 模糊
            sharpness_score = min(sharpness / 200 * 100, 100)
            # 曝光: 80-180 良好
            if 80 <= mean_brightness <= 180:
                exposure_score = 100
            elif 50 <= mean_brightness < 80 or 180 < mean_brightness <= 220:
                exposure_score = 70
            else:
                exposure_score = 40

            overall = (sharpness_score * 0.5 + exposure_score * 0.5)

            results.append({
                "file": os.path.basename(img_path),
                "width": w,
                "height": h,
                "sharpness": sharpness,
                "mean_brightness": mean_brightness,
                "under_exposed_pct": under_exposed,
                "over_exposed_pct": over_exposed,
                "mean_saturation": mean_saturation,
                "mean_hue": mean_hue,
                "scores": {
                    "sharpness": float(sharpness_score),
                    "exposure": float(exposure_score),
                    "overall": float(overall),
                }
            })

            feedback.set_progress(10 + int((i + 1) / len(image_files) * 85))

        # 汇总
        if not results:
            return AlgoResult(status=1, message="无有效影像")

        valid = [r for r in results if "error" not in r]
        avg_sharpness = np.mean([r["sharpness"] for r in valid])
        avg_brightness = np.mean([r["mean_brightness"] for r in valid])
        avg_score = np.mean([r["scores"]["overall"] for r in valid])

        report = {
            "total_images": len(image_files),
            "valid_images": len(valid),
            "failed": len(results) - len(valid),
            "avg_sharpness": float(avg_sharpness),
            "avg_brightness": float(avg_brightness),
            "avg_score": float(avg_score),
            "images": results,
        }

        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        feedback.push_info(f"平均清晰度: {avg_sharpness:.1f}")
        feedback.push_info(f"平均亮度: {avg_brightness:.1f}")
        feedback.push_info(f"平均评分: {avg_score:.1f}/100")

        return AlgoResult(
            status=0,
            message=f"影像质量评定完成({len(valid)}张), 平均评分 {avg_score:.1f}/100",
            outputs=[output_report],
            metadata={
                "output_report": output_report,
                "total_images": len(image_files),
                "avg_score": float(avg_score),
            }
        )
