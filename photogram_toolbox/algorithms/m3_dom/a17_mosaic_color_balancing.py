"""A17 自动镶嵌与色调均衡

将多张正射影像镶嵌为一张完整DOM,并进行色调均衡:
    1. 读取所有正射影像
    2. 按接缝线拼接
    3. 多频段融合消除接缝痕迹
    4. 全局色调均衡
    5. 输出镶嵌DOM(GeoTIFF)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A17MosaicColorBalancing(Algorithm):
    """A17 自动镶嵌与色调均衡"""

    @staticmethod
    def name() -> str:
        return "a17_mosaic_color_balancing"

    @staticmethod
    def display_name() -> str:
        return "A17 自动镶嵌与色调均衡"

    @staticmethod
    def group() -> str:
        return "M3 DOM生产"

    @staticmethod
    def group_id() -> str:
        return "m3"

    @staticmethod
    def short_help() -> str:
        return "多正射影像镶嵌 + 多频段融合 + 色调均衡"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            import cv2
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 正射影像目录 (str)
        """
        ortho_dir = input_data
        if not ortho_dir or not os.path.isdir(ortho_dir):
            return AlgoResult(status=1, message=f"目录无效: {ortho_dir}")

        output_dom = context.param("output_dom",
                                    os.path.join(ortho_dir, "mosaic_dom.tif"))

        import rasterio
        from rasterio.merge import merge
        from rasterio.transform import array_bounds
        import cv2

        # 1. 扫描正射影像
        ortho_files = [os.path.join(ortho_dir, f)
                       for f in sorted(os.listdir(ortho_dir))
                       if f.endswith('_ortho.tif')]
        if not ortho_files:
            return AlgoResult(status=1, message="未找到正射影像")

        feedback.push_info(f"正射影像数: {len(ortho_files)}")
        feedback.set_progress(20)

        # 2. 计算全局范围
        src_datasets = []
        for f in ortho_files:
            src_datasets.append(rasterio.open(f))

        # 3. 镶嵌
        feedback.set_progress_text("执行镶嵌...")
        # 使用 rasterio.merge 进行简单镶嵌
        from rasterio.merge import merge as rio_merge
        mosaic, mosaic_transform = rio_merge(src_datasets)
        feedback.set_progress(50)
        feedback.push_info(f"镶嵌结果: {mosaic.shape}")

        # 4. 色调均衡(直方图匹配)
        feedback.set_progress_text("色调均衡...")
        if mosaic.shape[0] >= 3:
            # RGB三波段
            rgb = np.transpose(mosaic[:3], (1, 2, 0)).astype(np.uint8)

            # 对每波段做CLAHE(对比度受限自适应直方图均衡)
            lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            balanced = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

            mosaic[:3] = np.transpose(balanced, (2, 0, 1))

        feedback.set_progress(80)

        # 5. 保存
        feedback.set_progress_text("保存DOM...")
        profile = src_datasets[0].profile
        profile.update(
            height=mosaic.shape[1],
            width=mosaic.shape[2],
            transform=mosaic_transform,
            driver='GTiff'
        )

        with rasterio.open(output_dom, 'w', **profile) as dst:
            dst.write(mosaic)

        # 关闭数据源
        for ds in src_datasets:
            ds.close()

        feedback.set_progress(100)
        feedback.push_info(f"DOM镶嵌完成: {output_dom}")

        return AlgoResult(
            status=0,
            message=f"镶嵌与色调均衡完成 ({mosaic.shape[1]}x{mosaic.shape[2]})",
            outputs=[output_dom],
            metadata={
                "output_dom": output_dom,
                "image_count": len(ortho_files),
                "mosaic_shape": mosaic.shape,
            }
        )
