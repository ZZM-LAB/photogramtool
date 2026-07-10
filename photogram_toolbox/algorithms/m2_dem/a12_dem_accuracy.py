"""A12 DEM精度自动评定

将生成的DEM与参考高程点对比,计算精度指标:
    - 中误差(RMSE)
    - 平均误差(ME)
    - 最大误差
    - 高程误差分布
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A12DEMAccuracyAssessment(Algorithm):
    """A12 DEM精度自动评定"""

    @staticmethod
    def name() -> str:
        return "a12_dem_accuracy"

    @staticmethod
    def display_name() -> str:
        return "A12 DEM精度自动评定"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "DEM与参考高程点对比,计算RMSE/ME等精度指标"

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
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        dem_path = input_data
        if not dem_path or not os.path.exists(dem_path):
            logger.error(f"DEM文件无效: {dem_path}")
            result = AlgoResult(status=1, message=f"DEM文件无效: {dem_path}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        # 参考高程点文件 (x y z 格式)
        check_file = context.param("check_file", "")
        if not check_file or not os.path.exists(check_file):
            logger.error(f"参考高程点文件不存在: {check_file}")
            result = AlgoResult(status=1, message=f"参考高程点文件不存在: {check_file}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        feedback.push_info(f"DEM: {dem_path}")
        feedback.push_info(f"参考点: {check_file}")
        logger.debug(f"参数: dem_path={dem_path}, check_file={check_file}")

        import rasterio
        from rasterio.transform import rowcol

        # 1. 读取DEM
        feedback.set_progress_text("读取DEM...")
        logger.timing_start("read_dem")
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            transform = src.transform
            crs = src.crs
        logger.timing_end("read_dem")
        logger.debug(f"DEM尺寸: {dem.shape}")
        feedback.set_progress(30)

        # 2. 读取参考点
        feedback.set_progress_text("读取参考高程点...")
        logger.timing_start("read_check_points")
        check_points = []
        with open(check_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 3:
                    check_points.append([float(parts[0]), float(parts[1]), float(parts[2])])
        check_points = np.array(check_points)
        logger.timing_end("read_check_points")
        feedback.push_info(f"参考点数: {len(check_points)}")
        logger.debug(f"参考点数: {len(check_points)}")
        feedback.set_progress(50)

        # 3. 采样DEM值
        feedback.set_progress_text("采样DEM高程值...")
        logger.timing_start("sample_dem")
        errors = []
        for x, y, z_ref in check_points:
            row, col = rowcol(transform, x, y)
            if 0 <= row < dem.shape[0] and 0 <= col < dem.shape[1]:
                z_dem = dem[row, col]
                if not np.isnan(z_dem):
                    errors.append(z_dem - z_ref)
        errors = np.array(errors)
        logger.timing_end("sample_dem")
        feedback.set_progress(80)

        if len(errors) == 0:
            logger.error("无有效参考点(都在DEM范围外或孔洞)")
            result = AlgoResult(status=1, message="无有效参考点(都在DEM范围外或孔洞)")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status={result.status}")
            return result

        # 4. 计算精度指标
        logger.timing_start("compute_metrics")
        rmse = np.sqrt(np.mean(errors**2))
        me = np.mean(errors)
        mae = np.mean(np.abs(errors))
        max_error = np.max(np.abs(errors))
        std = np.std(errors)
        logger.timing_end("compute_metrics")

        feedback.set_progress(100)
        feedback.push_info(f"有效点数: {len(errors)}")
        feedback.push_info(f"中误差 RMSE: {rmse:.4f}m")
        feedback.push_info(f"平均误差 ME: {me:.4f}m")
        feedback.push_info(f"最大误差: {max_error:.4f}m")
        logger.debug(f"精度指标: 有效点数={len(errors)}, RMSE={rmse:.4f}, ME={me:.4f}, MAE={mae:.4f}, max_error={max_error:.4f}, std={std:.4f}")

        result = AlgoResult(
            status=0,
            message=f"DEM精度评定完成, RMSE={rmse:.4f}m",
            outputs=[dem_path],
            metadata={
                "dem_path": dem_path,
                "check_file": check_file,
                "valid_count": len(errors),
                "rmse": float(rmse),
                "me": float(me),
                "mae": float(mae),
                "max_error": float(max_error),
                "std": float(std),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
