"""A02 SIFT特征自动提取与匹配

对数据库中的影像提取SIFT特征,并进行全量特征匹配
(影像<500张时用exhaustive_matcher最可靠)。
"""
import os
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY
from photogram_toolbox.core.colmap_wrapper import (
    ensure_dir, database_path, extract_features, match_exhaustive
)


@REGISTRY.register
class A02FeatureExtractionMatching(Algorithm):
    """A02 SIFT特征自动提取与匹配"""

    @staticmethod
    def name() -> str:
        return "a02_feature_extraction_matching"

    @staticmethod
    def display_name() -> str:
        return "A02 SIFT特征自动提取与匹配"

    @staticmethod
    def group() -> str:
        return "M1 空中三角测量"

    @staticmethod
    def group_id() -> str:
        return "m1"

    @staticmethod
    def short_help() -> str:
        return "提取SIFT特征并进行全量匹配,建立影像间对应关系"

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
            input_data: 工作目录路径 (str, 含 database.db)
                       或影像目录(会自动用 context.work_dir)
        """
        work_dir = input_data or context.work_dir
        if not work_dir:
            return AlgoResult(status=1, message="未指定工作目录")

        db = database_path(work_dir)
        if not os.path.exists(db):
            return AlgoResult(
                status=1,
                message=f"数据库不存在: {db},请先运行A01内定向"
            )

        feedback.push_info(f"工作目录: {work_dir}")

        # 1. SIFT特征提取
        feedback.set_progress_text("提取SIFT特征...")
        use_gpu = context.param("use_gpu", False)
        extract_features(work_dir, use_gpu=use_gpu)
        feedback.set_progress(50)
        feedback.push_info("特征提取完成")

        # 2. 全量特征匹配
        feedback.set_progress_text("全量特征匹配...")
        match_exhaustive(work_dir, use_gpu=use_gpu)
        feedback.set_progress(100)
        feedback.push_info("特征匹配完成")

        return AlgoResult(
            status=0,
            message="SIFT特征提取与匹配完成",
            outputs=[db],
            metadata={
                "work_dir": work_dir,
                "database": db,
                "use_gpu": use_gpu,
            }
        )
