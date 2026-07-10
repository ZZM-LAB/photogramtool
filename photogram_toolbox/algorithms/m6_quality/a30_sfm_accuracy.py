"""A30 空三精度自动评定

评估稀疏重建(SfM)的精度:
    1. 读取重建结果
    2. 统计重投影误差
    3. 分析3D点分布
    4. 计算相机姿态精度
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A30SfMAccuracyAssessment(Algorithm):
    """A30 空三精度自动评定"""

    @staticmethod
    def name() -> str:
        return "a30_sfm_accuracy"

    @staticmethod
    def display_name() -> str:
        return "A30 空三精度自动评定"

    @staticmethod
    def group() -> str:
        return "M6 质量评定"

    @staticmethod
    def group_id() -> str:
        return "m6"

    @staticmethod
    def short_help() -> str:
        return "统计重投影误差/3D点分布/相机姿态精度"

    @staticmethod
    def can_execute() -> bool:
        try:
            import pycolmap
            return True
        except ImportError:
            return False

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 稀疏重建目录 (str, sparse/0)
        """
        sparse_dir = input_data
        if not sparse_dir or not os.path.isdir(sparse_dir):
            return AlgoResult(status=1, message=f"重建目录无效: {sparse_dir}")

        output_report = context.param("output_report",
                                       os.path.join(sparse_dir, "sfm_accuracy_report.json"))

        import pycolmap

        # 1. 加载重建
        feedback.set_progress_text("加载重建结果...")
        recon = pycolmap.Reconstruction(sparse_dir)
        feedback.push_info(f"影像数: {len(recon.images)}")
        feedback.push_info(f"3D点数: {len(recon.points3D)}")
        feedback.set_progress(30)

        # 2. 重投影误差统计
        feedback.set_progress_text("统计重投影误差...")
        errors = []
        point_errors = {}

        for pt_id, point3d in recon.points3D.items():
            point_errors[pt_id] = point3d.error

        if point_errors:
            errors = list(point_errors.values())
            errors = np.array(errors)

            mean_error = float(np.mean(errors))
            median_error = float(np.median(errors))
            std_error = float(np.std(errors))
            max_error = float(np.max(errors))
            p90_error = float(np.percentile(errors, 90))
        else:
            mean_error = median_error = std_error = max_error = p90_error = 0.0

        feedback.push_info(f"平均重投影误差: {mean_error:.4f}px")
        feedback.push_info(f"中误差: {median_error:.4f}px")
        feedback.set_progress(50)

        # 3. 3D点分布分析
        feedback.set_progress_text("分析3D点分布...")
        points = []
        for pt_id, point3d in recon.points3D.items():
            xyz = point3d.xyz
            points.append([xyz[0], xyz[1], xyz[2]])

        points = np.array(points)

        if len(points) > 0:
            # 空间范围
            bounds_min = points.min(axis=0)
            bounds_max = points.max(axis=0)
            extent = bounds_max - bounds_min

            # 点密度
            volume = np.prod(extent) if np.all(extent > 0) else 1
            density = len(points) / volume if volume > 0 else 0

            # 点云质心
            centroid = points.mean(axis=0)
        else:
            bounds_min = bounds_max = extent = np.zeros(3)
            density = 0
            centroid = np.zeros(3)

        feedback.set_progress(70)

        # 4. 相机姿态分析
        feedback.set_progress_text("分析相机姿态...")
        camera_positions = []
        for img_id, img in recon.images.items():
            # 相机位置 = -R^T * t
            R = img.rotation_matrix()
            t = img.tvec
            pos = -R.T @ t
            camera_positions.append(pos)

        camera_positions = np.array(camera_positions)

        # 相机间距
        if len(camera_positions) > 1:
            from scipy.spatial.distance import pdist
            dists = pdist(camera_positions)
            avg_baseline = float(np.mean(dists))
            min_baseline = float(np.min(dists))
            max_baseline = float(np.max(dists))
        else:
            avg_baseline = min_baseline = max_baseline = 0.0

        feedback.set_progress(90)

        # 5. 评分
        # 重投影误差: <1px 优秀, <2px 良好, <4px 合格
        if mean_error < 1:
            accuracy_score = 100
        elif mean_error < 2:
            accuracy_score = 80
        elif mean_error < 4:
            accuracy_score = 60
        else:
            accuracy_score = 30

        report = {
            "images": len(recon.images),
            "points3D": len(recon.points3D),
            "reprojection_error": {
                "mean": mean_error,
                "median": median_error,
                "std": std_error,
                "max": max_error,
                "p90": p90_error,
            },
            "point_distribution": {
                "bounds_min": bounds_min.tolist(),
                "bounds_max": bounds_max.tolist(),
                "extent": extent.tolist(),
                "density": float(density),
                "centroid": centroid.tolist(),
            },
            "camera_baseline": {
                "avg": avg_baseline,
                "min": min_baseline,
                "max": max_baseline,
            },
            "accuracy_score": accuracy_score,
        }

        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        feedback.push_info(f"精度评分: {accuracy_score}/100")

        return AlgoResult(
            status=0,
            message=f"空三精度评定完成, 平均误差 {mean_error:.4f}px, 评分 {accuracy_score}/100",
            outputs=[output_report],
            metadata=report
        )
