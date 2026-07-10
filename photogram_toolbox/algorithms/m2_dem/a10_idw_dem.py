"""A10 地面点IDW插值生成DEM

将离散地面点云插值为规则格网DEM:
    1. 读取地面点云 (x, y, z)
    2. 确定DEM范围和分辨率
    3. 反距离加权(IDW)插值
    4. 输出 GeoTIFF 格式DEM
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.pointcloud_utils import load_pointcloud


@REGISTRY.register
class A10IDWInterpolationDEM(Algorithm):
    """A10 地面点IDW插值生成DEM"""

    @staticmethod
    def name() -> str:
        return "a10_idw_interpolation_dem"

    @staticmethod
    def display_name() -> str:
        return "A10 IDW插值生成DEM"

    @staticmethod
    def group() -> str:
        return "M2 DEM生产"

    @staticmethod
    def group_id() -> str:
        return "m2"

    @staticmethod
    def short_help() -> str:
        return "反距离加权插值将地面点云转为规则格网DEM"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            import scipy
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 地面点云路径 (str, .ply)
        """
        input_ply = input_data
        if not input_ply or not os.path.exists(input_ply):
            return AlgoResult(status=1, message=f"点云文件无效: {input_ply}")

        output_dem = context.param("output_dem",
                                    input_ply.replace(".ply", "_dem.tif"))
        resolution = context.param("resolution", 1.0)  # 米/像素
        power = context.param("power", 2.0)  # IDW 幂次
        search_radius = context.param("search_radius", 5.0)  # 搜索半径(像素)

        feedback.push_info(f"输入: {input_ply}")
        feedback.push_info(f"分辨率: {resolution}m, IDW幂次: {power}")

        # 1. 加载点云
        feedback.set_progress_text("加载地面点云...")
        pcd = load_pointcloud(input_ply)
        points = np.asarray(pcd.points)
        feedback.push_info(f"点数: {len(points)}")
        feedback.set_progress(20)

        x, y, z = points[:, 0], points[:, 1], points[:, 2]
        xmin, xmax = x.min(), x.max()
        ymin, ymax = y.min(), y.max()

        # 2. 生成格网
        feedback.set_progress_text("生成DEM格网...")
        cols = int(np.ceil((xmax - xmin) / resolution))
        rows = int(np.ceil((ymax - ymin) / resolution))

        grid_x, grid_y = np.meshgrid(
            np.linspace(xmin, xmax, cols),
            np.linspace(ymin, ymax, rows)[::-1]  # 从北到南
        )
        feedback.set_progress(40)

        # 3. IDW 插值
        feedback.set_progress_text("IDW插值...")
        from scipy.spatial import cKDTree
        tree = cKDTree(np.column_stack([x, y]))

        grid_points = np.column_stack([grid_x.ravel(), grid_y.ravel()])
        radius = search_radius * resolution

        # 查询半径内的点
        result = tree.query_ball_point(grid_points, r=radius)
        feedback.set_progress(60)

        dem = np.full(len(grid_points), np.nan)
        for i, idx in enumerate(result):
            if len(idx) == 0:
                continue
            dx = x[idx] - grid_points[i, 0]
            dy = y[idx] - grid_points[i, 1]
            dist = np.sqrt(dx**2 + dy**2)
            # 避免除零
            dist = np.where(dist < 1e-10, 1e-10, dist)
            weights = 1.0 / dist**power
            dem[i] = np.sum(weights * z[idx]) / np.sum(weights)

        dem = dem.reshape(rows, cols)
        feedback.set_progress(80)

        # 4. 保存 GeoTIFF
        feedback.set_progress_text("保存DEM...")
        import rasterio
        from rasterio.transform import from_origin
        transform = from_origin(xmin, ymax, resolution, resolution)

        with rasterio.open(
            output_dem, 'w', driver='GTiff',
            height=rows, width=cols,
            count=1, dtype='float32',
            crs=context.crs_wkt or 'EPSG:4326',
            transform=transform,
            nodata=np.nan
        ) as dst:
            dst.write(dem.astype('float32'), 1)

        feedback.set_progress(100)
        feedback.push_info(f"DEM生成完成: {output_dem} ({rows}x{cols})")

        return AlgoResult(
            status=0,
            message=f"DEM生成完成 ({rows}x{cols}, {resolution}m)",
            outputs=[output_dem],
            metadata={
                "output_dem": output_dem,
                "resolution": resolution,
                "rows": rows,
                "cols": cols,
                "extent": (xmin, ymin, xmax, ymax),
            }
        )
