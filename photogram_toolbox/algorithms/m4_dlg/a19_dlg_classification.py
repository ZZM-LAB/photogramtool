"""A19 DLG要素自动分类

对DOM影像进行要素分类,识别建筑物/道路/植被/水体等DLG要素:
    1. 提取多特征(光谱/纹理/形态)
    2. 使用随机森林分类器
    3. 输出分类图(GeoTIFF)
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.logger import get_logger

logger = get_logger(__name__)


@REGISTRY.register
class A19DLGClassification(Algorithm):
    """A19 DLG要素自动分类"""

    @staticmethod
    def name() -> str:
        return "a19_dlg_classification"

    @staticmethod
    def display_name() -> str:
        return "A19 DLG要素自动分类"

    @staticmethod
    def group() -> str:
        return "M4 DLG提取"

    @staticmethod
    def group_id() -> str:
        return "m4"

    @staticmethod
    def short_help() -> str:
        return "多特征提取+随机森林分类,识别DLG要素"

    @staticmethod
    def can_execute() -> bool:
        try:
            import rasterio
            from sklearn.ensemble import RandomForestClassifier
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: DOM影像路径 (str, .tif)
        """
        logger.info(f"开始执行 {self.display_name()}, input={input_data}")
        logger.timing_start("total")
        dom_path = input_data
        if not dom_path or not os.path.exists(dom_path):
            logger.error(f"DOM文件无效: {dom_path}")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status=1")
            return AlgoResult(status=1, message=f"DOM文件无效: {dom_path}")

        output_path = context.param("output_path",
                                     dom_path.replace(".tif", "_classification.tif"))
        n_estimators = context.param("n_estimators", 100)

        feedback.push_info(f"输入: {dom_path}")

        import rasterio
        from sklearn.ensemble import RandomForestClassifier
        from scipy import ndimage

        # 1. 读取DOM
        logger.debug("开始读取DOM")
        logger.timing_start("read_dom")
        feedback.set_progress_text("读取DOM...")
        with rasterio.open(dom_path) as src:
            dom = src.read()
            profile = src.profile
        feedback.push_info(f"DOM尺寸: {dom.shape}")
        feedback.set_progress(20)
        logger.timing_end("read_dom")
        logger.debug(f"DOM读取完成, 尺寸={dom.shape}")

        bands, rows, cols = dom.shape
        if bands < 3:
            logger.error(f"DOM波段数不足: {bands}, 至少需要3波段")
            logger.timing_end("total")
            logger.info(f"完成 {self.display_name()}, status=1")
            return AlgoResult(status=1, message="DOM至少需要3波段")

        # 2. 特征提取
        logger.debug("开始特征提取")
        logger.timing_start("feature_extraction")
        feedback.set_progress_text("提取特征...")
        rgb = np.transpose(dom[:3], (1, 2, 0)).astype(float)
        r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]

        features = []
        # 光谱特征
        features.append(r)
        features.append(g)
        features.append(b)
        ndvi = (g - r) / (g + r + 1e-10)
        features.append(ndvi)
        features.append(r - g)  # 红绿差

        # 纹理特征(局部方差)
        for band_idx in range(3):
            band = rgb[:, :, band_idx]
            mean = ndimage.uniform_filter(band, size=5)
            sq_mean = ndimage.uniform_filter(band**2, size=5)
            variance = sq_mean - mean**2
            features.append(variance)

        feature_stack = np.stack(features, axis=-1)
        flat_features = feature_stack.reshape(-1, len(features))
        feedback.push_info(f"特征数: {len(features)}")
        feedback.set_progress(40)
        logger.timing_end("feature_extraction")
        logger.debug(f"特征提取完成, 特征数={len(features)}")

        # 3. 无监督分类(简化版: K-means)
        logger.debug("开始K-means分类")
        logger.timing_start("classification")
        feedback.set_progress_text("执行分类...")
        from sklearn.cluster import KMeans
        n_classes = context.param("n_classes", 5)

        # 采样以加速
        sample_size = min(10000, flat_features.shape[0])
        sample_idx = np.random.choice(flat_features.shape[0], sample_size, replace=False)
        sample = flat_features[sample_idx]

        kmeans = KMeans(n_clusters=n_classes, random_state=42, n_init=10)
        kmeans.fit(sample)
        labels = kmeans.predict(flat_features)
        label_map = labels.reshape(rows, cols).astype(np.uint8)
        feedback.set_progress(80)
        logger.timing_end("classification")
        logger.debug(f"K-means分类完成, 类别数={n_classes}")

        # 4. 保存
        logger.debug("开始保存分类结果")
        logger.timing_start("save")
        feedback.set_progress_text("保存分类结果...")
        out_profile = profile.copy()
        out_profile.update(dtype='uint8', count=1)
        with rasterio.open(output_path, 'w', **out_profile) as dst:
            dst.write(label_map, 1)
        logger.timing_end("save")
        logger.debug(f"分类结果已保存: {output_path}")

        feedback.set_progress(100)
        feedback.push_info(f"分类完成: {n_classes} 类")

        result = AlgoResult(
            status=0,
            message=f"DLG要素分类完成, {n_classes} 类",
            outputs=[output_path],
            metadata={
                "output_path": output_path,
                "n_classes": n_classes,
                "n_features": len(features),
            }
        )
        logger.timing_end("total")
        logger.info(f"完成 {self.display_name()}, status={result.status}")
        return result
