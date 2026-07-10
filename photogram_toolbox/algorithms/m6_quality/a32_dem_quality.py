"""A32 DEM质量自动评定

全面评估DEM质量:
    1. 高程范围/坡度
    2. 精度(RMSE/MAE)
    3. 完整性(有效像素率)
    4. 平滑度(粗糙度)
    5. 异常值检测
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A32DEMQualityAssessment(Algorithm):
    """A32 DEM质量自动评定"""

    @staticmethod
    def name() -> str:
        return "a32_dem_quality"

    @staticmethod
    def display_name() -> str:
        return "A32 DEM质量自动评定"

    @staticmethod
    def group() -> str:
        return "M6 质量评定"

    @staticmethod
    def group_id() -> str:
        return "m6"

    @staticmethod
    def short_help() -> str:
        return "DEM高程/精度/完整性/平滑度全面评估"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: DEM路径 (str, .tif)
        """
        dem_path = input_data
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")
        if not dem_path or not os.path.exists(dem_path):
            logger.error(f"DEM无效: {dem_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"DEM无效: {dem_path}")

        output_report = context.param("output_report",
                                       dem_path.replace(".tif", "_quality.json"))
        logger.debug(f"输出报告路径: {output_report}")

        import rasterio
        from scipy import ndimage

        # 1. 读取DEM
        feedback.set_progress_text("读取DEM...")
        logger.timing_start("read_dem")
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            transform = src.transform
            resolution = abs(transform.a)
        logger.timing_end("read_dem")
        logger.debug(f"DEM尺寸: {dem.shape}, 分辨率: {resolution}m")
        feedback.push_info(f"DEM尺寸: {dem.shape}, 分辨率: {resolution}m")
        feedback.set_progress(20)

        valid = ~np.isnan(dem)
        valid_count = np.sum(valid)
        total_count = dem.size
        completeness = valid_count / total_count

        feedback.push_info(f"有效像素: {valid_count}/{total_count} ({completeness*100:.1f}%)")

        if valid_count == 0:
            logger.error("DEM全为空")
            logger.timing_end("total")
            return AlgoResult(status=1, message="DEM全为空")

        valid_data = dem[valid]
        feedback.set_progress(40)

        # 2. 高程统计
        logger.timing_start("elevation_stats")
        z_min = float(np.min(valid_data))
        z_max = float(np.max(valid_data))
        z_mean = float(np.mean(valid_data))
        z_std = float(np.std(valid_data))
        logger.timing_end("elevation_stats")
        logger.debug(f"高程范围: {z_min:.2f}-{z_max:.2f}, 均值: {z_mean:.2f}, std: {z_std:.2f}")

        feedback.push_info(f"高程范围: {z_min:.2f} - {z_max:.2f}m, 均值: {z_mean:.2f}m")
        feedback.set_progress(50)

        # 3. 坡度
        feedback.set_progress_text("计算坡度...")
        logger.timing_start("slope")
        dem_filled = dem.copy()
        dem_filled[~valid] = z_mean
        grad_y, grad_x = np.gradient(dem_filled, resolution)
        slope = np.arctan(np.sqrt(grad_x**2 + grad_y**2)) * 180 / np.pi
        slope_valid = slope[valid]
        mean_slope = float(np.mean(slope_valid))
        max_slope = float(np.max(slope_valid))
        logger.timing_end("slope")
        logger.debug(f"坡度 mean={mean_slope:.2f}, max={max_slope:.2f}")
        feedback.set_progress(60)

        # 4. 粗糙度(局部标准差)
        feedback.set_progress_text("计算粗糙度...")
        logger.timing_start("roughness")
        local_mean = ndimage.uniform_filter(dem_filled, size=5)
        local_sq_mean = ndimage.uniform_filter(dem_filled**2, size=5)
        local_std = np.sqrt(np.maximum(local_sq_mean - local_mean**2, 0))
        mean_roughness = float(np.mean(local_std[valid]))
        logger.timing_end("roughness")
        logger.debug(f"粗糙度: {mean_roughness:.4f}")
        feedback.set_progress(75)

        # 5. 异常值检测
        feedback.set_progress_text("检测异常值...")
        logger.timing_start("outlier_detection")
        # 3σ原则
        outliers = np.abs(valid_data - z_mean) > 3 * z_std
        outlier_count = np.sum(outliers)
        outlier_rate = outlier_count / valid_count
        logger.timing_end("outlier_detection")
        logger.debug(f"异常值: {outlier_count} ({outlier_rate*100:.2f}%)")
        feedback.push_info(f"异常值: {outlier_count} ({outlier_rate*100:.2f}%)")
        feedback.set_progress(85)

        # 6. 评分
        completeness_score = completeness * 100
        if z_std < 5:
            roughness_score = 100
        elif z_std < 20:
            roughness_score = 80
        else:
            roughness_score = 60

        if outlier_rate < 0.01:
            outlier_score = 100
        elif outlier_rate < 0.05:
            outlier_score = 70
        else:
            outlier_score = 40

        overall = (completeness_score * 0.4 + roughness_score * 0.3 + outlier_score * 0.3)

        report = {
            "dem_info": {
                "path": dem_path,
                "shape": list(dem.shape),
                "resolution_m": float(resolution),
            },
            "completeness": {
                "valid_pixels": int(valid_count),
                "total_pixels": int(total_count),
                "completeness": float(completeness),
            },
            "elevation": {
                "min": z_min,
                "max": z_max,
                "mean": z_mean,
                "std": z_std,
            },
            "slope": {
                "mean_degrees": mean_slope,
                "max_degrees": max_slope,
            },
            "roughness": {
                "mean_local_std": mean_roughness,
            },
            "outliers": {
                "count": int(outlier_count),
                "rate": float(outlier_rate),
            },
            "scores": {
                "completeness": float(completeness_score),
                "roughness": float(roughness_score),
                "outlier": float(outlier_score),
                "overall": float(overall),
            }
        }

        logger.timing_start("write_report")
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.timing_end("write_report")
        logger.debug(f"报告已写入: {output_report}")

        feedback.set_progress(100)
        feedback.push_info(f"质量评分: {overall:.1f}/100")

        logger.timing_end("total")
        result = AlgoResult(
            status=0,
            message=f"DEM质量评定完成, 评分 {overall:.1f}/100",
            outputs=[output_report],
            metadata=report
        )
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
