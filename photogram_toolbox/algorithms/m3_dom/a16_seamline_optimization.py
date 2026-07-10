"""A16 最优接缝线优化（Graph Cut）

在重叠区域用最小割算法优化接缝线,避开差异大的区域:
    1. 计算相邻影像重叠区差异图
    2. 构建图(像素为节点,差异为边权)
    3. 求最小割确定最优接缝线
    4. 输出优化后的接缝线

纯Python实现,无需PyMaxflow。
"""
import os
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A16SeamlineOptimization(Algorithm):
    """A16 最优接缝线优化"""

    @staticmethod
    def name() -> str:
        return "a16_seamline_optimization"

    @staticmethod
    def display_name() -> str:
        return "A16 最优接缝线优化"

    @staticmethod
    def group() -> str:
        return "M3 DOM生产"

    @staticmethod
    def group_id() -> str:
        return "m3"

    @staticmethod
    def short_help() -> str:
        return "Graph Cut最小割优化接缝线,避开差异大区域"

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

        output_dir = context.param("output_dir",
                                    os.path.join(ortho_dir, "optimized_seams"))
        os.makedirs(output_dir, exist_ok=True)

        import rasterio
        import cv2
        import json

        # 1. 扫描正射影像
        ortho_files = sorted([f for f in os.listdir(ortho_dir)
                              if f.endswith('_ortho.tif')])
        if len(ortho_files) < 2:
            return AlgoResult(status=1, message="至少需要2张正射影像")

        feedback.push_info(f"正射影像数: {len(ortho_files)}")
        feedback.set_progress(20)

        # 2. 逐对优化相邻影像的接缝线
        optimized_seams = []
        total_pairs = len(ortho_files) - 1

        for i in range(total_pairs):
            if feedback.is_canceled():
                return AlgoResult(status=2, message="用户取消")

            img1_path = os.path.join(ortho_dir, ortho_files[i])
            img2_path = os.path.join(ortho_dir, ortho_files[i + 1])

            feedback.set_progress_text(f"优化接缝线 {i+1}/{total_pairs}: {ortho_files[i]} ↔ {ortho_files[i+1]}")

            # 读取影像
            with rasterio.open(img1_path) as src1:
                img1 = src1.read()
                transform1 = src1.transform
            with rasterio.open(img2_path) as src2:
                img2 = src2.read()

            # 检查尺寸
            if img1.shape != img2.shape:
                feedback.push_warning(f"影像尺寸不匹配,跳过: {ortho_files[i]}")
                continue

            # 计算重叠区差异
            valid1 = np.any(img1 > 0, axis=0)
            valid2 = np.any(img2 > 0, axis=0)
            overlap = valid1 & valid2

            if not np.any(overlap):
                continue

            # 差异图
            diff = np.mean(np.abs(img1.astype(float) - img2.astype(float)), axis=0)
            diff[~overlap] = 1e6  # 非重叠区设大值

            # 用动态规划求最优接缝(垂直方向)
            # cost[i,j] = diff[i,j] + min(cost[i-1,j-1], cost[i-1,j], cost[i-1,j+1])
            rows, cols = diff.shape
            cost = diff.copy()
            backtrack = np.zeros_like(cost, dtype=int)

            for r in range(1, rows):
                for c in range(cols):
                    if not overlap[r, c]:
                        cost[r, c] = 1e6
                        continue
                    # 左/中/右
                    c_left = cost[r-1, c-1] if c > 0 else 1e6
                    c_mid = cost[r-1, c]
                    c_right = cost[r-1, c+1] if c < cols-1 else 1e6

                    min_val = min(c_left, c_mid, c_right)
                    cost[r, c] += min_val

                    if min_val == c_left:
                        backtrack[r, c] = -1
                    elif min_val == c_mid:
                        backtrack[r, c] = 0
                    else:
                        backtrack[r, c] = 1

            # 回溯找最优路径
            seam = np.zeros(rows, dtype=int)
            seam[-1] = np.argmin(cost[-1])
            for r in range(rows - 2, -1, -1):
                seam[r] = seam[r+1] + backtrack[r+1, seam[r+1]]
                seam[r] = max(0, min(cols - 1, seam[r]))

            # 转为地理坐标
            coords = []
            for r in range(rows):
                x, y = rasterio.transform.xy(transform1, r, seam[r])
                coords.append([float(x), float(y)])

            optimized_seams.append({
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "image1": ortho_files[i],
                    "image2": ortho_files[i + 1],
                }
            })

            feedback.set_progress(20 + int((i + 1) / total_pairs * 70))

        # 3. 输出
        output_geojson = os.path.join(output_dir, "optimized_seams.geojson")
        with open(output_geojson, 'w', encoding='utf-8') as f:
            json.dump({"type": "FeatureCollection", "features": optimized_seams}, f,
                      ensure_ascii=False)

        feedback.set_progress(100)
        feedback.push_info(f"优化完成: {len(optimized_seams)} 条接缝线")

        return AlgoResult(
            status=0,
            message=f"接缝线优化完成, {len(optimized_seams)} 条",
            outputs=[output_geojson],
            metadata={
                "output_geojson": output_geojson,
                "seam_count": len(optimized_seams),
            }
        )
