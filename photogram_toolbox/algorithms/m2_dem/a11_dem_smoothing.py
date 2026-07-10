"""A11 DEM自动平滑与孔洞填充

对DEM进行后处理:
    1. 中值滤波去噪(保留边缘)
    2. 孔洞填充(反距离插值)
    3. 可选高斯平滑
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A11DEMSmoothing(Algorithm):
    """A11 DEM自动平滑与孔洞填充"""

    @staticmethod
    def name() -> str:
        return "a11_dem_smoothing"

    @staticmethod
    def display_name() -> str:
        return "A11 DEM平滑与孔洞填充"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "中值滤波去噪 + 孔洞填充"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            from scipy.ndimage import median_filter
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 输入DEM路径 (str, .tif)
        """
        input_dem = input_data
        if not input_dem or not os.path.exists(input_dem):
            return AlgoResult(status=1, message=f"DEM文件无效: {input_dem}")

        output_dem = context.param("output_dem",
                                    input_dem.replace(".tif", "_smoothed.tif"))
        filter_size = context.param("filter_size", 3)

        feedback.push_info(f"输入: {input_dem}")
        feedback.push_info(f"滤波窗口: {filter_size}x{filter_size}")

        import rasterio
        from scipy.ndimage import median_filter, binary_dilation
        from scipy.spatial import cKDTree

        # 1. 读取DEM
        feedback.set_progress_text("读取DEM...")
        with rasterio.open(input_dem) as src:
            dem = src.read(1)
            profile = src.profile
            transform = src.transform
            nodata = src.nodata
        feedback.push_info(f"DEM尺寸: {dem.shape}")
        feedback.set_progress(20)

        # 标记孔洞
        valid = ~np.isnan(dem) if nodata is None or np.isnan(nodata) else (dem != nodata)
        hole_count = np.sum(~valid)
        feedback.push_info(f"孔洞像素: {hole_count} ({hole_count/dem.size*100:.1f}%)")
        feedback.set_progress(30)

        # 2. 中值滤波(仅对有效像素)
        feedback.set_progress_text("中值滤波...")
        dem_filtered = dem.copy()
        if np.any(valid):
            temp = dem.copy()
            temp[~valid] = np.nanmedian(dem[valid]) if np.any(valid) else 0
            dem_filtered = median_filter(temp, size=filter_size)
            dem_filtered[~valid] = np.nan  # 恢复孔洞
        feedback.set_progress(50)

        # 3. 孔洞填充
        if hole_count > 0:
            feedback.set_progress_text("填充孔洞...")
            ys, xs = np.where(valid)
            zs = dem_filtered[valid]
            tree = cKDTree(np.column_stack([xs, ys]))

            hole_ys, hole_xs = np.where(~valid)
            if len(hole_ys) > 0:
                hole_points = np.column_stack([hole_xs, hole_ys])
                dist, idx = tree.query(hole_points, k=min(8, len(xs)))

                # IDW 插值
                weights = 1.0 / np.maximum(dist, 1e-10)**2
                filled = np.sum(weights * zs[idx], axis=1) / np.sum(weights, axis=1)
                dem_filtered[hole_ys, hole_xs] = filled
        feedback.set_progress(80)

        # 4. 保存
        feedback.set_progress_text("保存结果...")
        profile.update(dtype='float32', nodata=np.nan)
        with rasterio.open(output_dem, 'w', **profile) as dst:
            dst.write(dem_filtered.astype('float32'), 1)

        feedback.set_progress(100)
        feedback.push_info(f"平滑完成: {output_dem}")

        return AlgoResult(
            status=0,
            message=f"DEM平滑完成,填充 {hole_count} 个孔洞",
            outputs=[output_dem],
            metadata={
                "output_dem": output_dem,
                "filter_size": filter_size,
                "hole_count": int(hole_count),
            }
        )
