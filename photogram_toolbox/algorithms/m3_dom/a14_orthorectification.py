"""A14 数字微分纠正（单片正射）

将原始影像通过共线方程投影到DEM表面,生成正射影像。
对于每张影像:
    1. 读取DEM格网
    2. 对每个DEM格网点,通过共线方程反投影到影像
    3. 采样影像像素值
    4. 输出正射影像(GeoTIFF)

需要: DEM + 原始影像 + 相机外方位元素(来自SfM)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A14Orthorectification(Algorithm):
    """A14 数字微分纠正"""

    @staticmethod
    def name() -> str:
        return "a14_orthorectification"

    @staticmethod
    def display_name() -> str:
        return "A14 数字微分纠正"

    @staticmethod
    def group() -> str:
        return "M3 DOM生产"

    @staticmethod
    def group_id() -> str:
        return "m3"

    @staticmethod
    def short_help() -> str:
        return "通过共线方程将影像投影到DEM,生成正射影像"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            import cv2
            import pycolmap
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: dense 工作目录 (str, 含稀疏重建结果)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")

        dense_dir = input_data
        if not dense_dir or not os.path.isdir(dense_dir):
            logger.error(f"工作目录无效: {dense_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"工作目录无效: {dense_dir}")

        dem_path = context.param("dem_path", "")
        image_dir = context.param("image_dir", "")
        output_dir = context.param("output_dir",
                                    os.path.join(dense_dir, "orthophotos"))

        if not dem_path or not os.path.exists(dem_path):
            logger.error(f"DEM文件不存在: {dem_path}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"DEM文件不存在: {dem_path}")
        if not image_dir or not os.path.isdir(image_dir):
            logger.error(f"影像目录不存在: {image_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"影像目录不存在: {image_dir}")

        os.makedirs(output_dir, exist_ok=True)

        import rasterio
        from rasterio.transform import rowcol, xy
        import cv2
        import pycolmap

        # 1. 读取DEM
        feedback.set_progress_text("读取DEM...")
        logger.debug("开始读取DEM", dem_path=dem_path)
        logger.timing_start("read_dem")
        with rasterio.open(dem_path) as src:
            dem = src.read(1)
            dem_transform = src.transform
            dem_crs = src.crs
            dem_bounds = src.bounds
        logger.timing_end("read_dem")
        logger.debug(f"DEM读取完成: shape={dem.shape}, bounds={dem_bounds}")
        feedback.push_info(f"DEM尺寸: {dem.shape}, 范围: {dem_bounds}")
        feedback.set_progress(20)

        # 2. 加载重建结果(相机参数)
        sparse_dir = context.param("sparse_dir",
                                    os.path.join(dense_dir, "..", "sparse", "0"))
        if not os.path.isdir(sparse_dir):
            logger.error(f"稀疏重建目录不存在: {sparse_dir}")
            logger.timing_end("total")
            return AlgoResult(status=1, message=f"稀疏重建目录不存在: {sparse_dir}")

        feedback.set_progress_text("加载相机参数...")
        logger.debug("开始加载相机参数", sparse_dir=sparse_dir)
        logger.timing_start("load_reconstruction")
        recon = pycolmap.Reconstruction(sparse_dir)
        images = recon.images
        logger.timing_end("load_reconstruction")
        logger.debug(f"相机参数加载完成: 影像数={len(images)}")
        feedback.push_info(f"影像数: {len(images)}")
        feedback.set_progress(40)

        # 3. 逐张纠正
        output_files = []
        total_images = len(images)
        logger.debug(f"开始逐张纠正, 共 {total_images} 张影像")
        logger.timing_start("rectify_all")
        for idx, (img_id, img) in enumerate(images.items()):
            if feedback.is_canceled():
                logger.error("用户取消(纠正循环外层)")
                logger.timing_end("rectify_all")
                logger.timing_end("total")
                return AlgoResult(status=2, message="用户取消")

            img_name = img.name
            img_path = os.path.join(image_dir, img_name)
            if not os.path.exists(img_path):
                feedback.push_warning(f"影像不存在: {img_name}")
                logger.debug(f"影像不存在,跳过: {img_name}")
                continue

            feedback.set_progress_text(f"纠正 {img_name} ({idx+1}/{total_images})...")
            logger.debug(f"纠正影像 ({idx+1}/{total_images}): {img_name}")

            # 读取影像
            logger.timing_start(f"read_image_{img_name}")
            photo = cv2.imread(img_path)
            logger.timing_end(f"read_image_{img_name}")
            if photo is None:
                logger.debug(f"影像读取为空,跳过: {img_name}")
                continue
            photo = cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)

            # 相机参数
            camera = recon.cameras[img.camera_id]
            cam_params = camera.params
            R = img.rotation_matrix()
            t = img.tvec

            # 简化纠正: 用DEM高程均值做平面纠正
            # 完整实现需逐像素共线方程反投影
            z_mean = np.nanmean(dem)

            # 生成正射影像(简化版: 平面纠正)
            rows, cols = dem.shape
            ortho = np.zeros((rows, cols, 3), dtype=np.uint8)

            # 对每个DEM格网点反投影
            logger.timing_start(f"back_project_{img_name}")
            for r in range(0, rows, 1):
                if feedback.is_canceled():
                    logger.error("用户取消(纠正循环内层)")
                    logger.timing_end(f"back_project_{img_name}")
                    logger.timing_end("rectify_all")
                    logger.timing_end("total")
                    return AlgoResult(status=2, message="用户取消")
                for c in range(cols):
                    z = dem[r, c]
                    if np.isnan(z):
                        continue
                    # DEM格网点的世界坐标
                    wx, wy = xy(dem_transform, r, c)
                    wz = z

                    # 世界坐标 → 相机坐标
                    pw = np.array([wx, wy, wz])
                    pc = R @ (pw - t)

                    # 相机坐标 → 像素坐标
                    if pc[2] <= 0:
                        continue
                    u = cam_params[0] * pc[0] / pc[2] + cam_params[1]
                    v = cam_params[0] * pc[1] / pc[2] + cam_params[2]

                    ui, vi = int(u), int(v)
                    if 0 <= ui < photo.shape[1] and 0 <= vi < photo.shape[0]:
                        ortho[r, c] = photo[vi, ui]
            logger.timing_end(f"back_project_{img_name}")

            # 保存
            out_path = os.path.join(output_dir,
                                     img_name.replace(".jpg", "_ortho.tif")
                                             .replace(".JPG", "_ortho.tif"))
            logger.timing_start(f"save_ortho_{img_name}")
            with rasterio.open(
                out_path, 'w', driver='GTiff',
                height=rows, width=cols,
                count=3, dtype='uint8',
                crs=dem_crs, transform=dem_transform
            ) as dst:
                for band in range(3):
                    dst.write(ortho[:, :, band], band + 1)
            logger.timing_end(f"save_ortho_{img_name}")
            logger.debug(f"正射影像已保存: {out_path}")

            output_files.append(out_path)
            feedback.set_progress(40 + int((idx + 1) / total_images * 55))

        logger.timing_end("rectify_all")
        feedback.set_progress(100)
        feedback.push_info(f"纠正完成: {len(output_files)} 张正射影像")
        logger.debug(f"逐张纠正完成, 共生成 {len(output_files)} 张正射影像")

        result = AlgoResult(
            status=0,
            message=f"数字微分纠正完成, {len(output_files)} 张正射影像",
            outputs=output_files,
            metadata={
                "output_dir": output_dir,
                "ortho_count": len(output_files),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
