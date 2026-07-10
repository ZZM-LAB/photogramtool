"""M4 DLG自动提取模块 (A19-A24)

算法列表:
    A19 DLG要素自动分类    - 多特征+K-means聚类
    A20 语义分割           - PyTorch U-Net GPU推理
    A21 矢量化提取         - 栅格转矢量+简化
    A22 拓扑关系构建       - 相邻检测+缝隙检查
    A23 DLG符号化          - 制图标准渲染
    A24 DLG精度评定        - IoU/F1/混淆矩阵
"""
from .a19_dlg_classification import A19DLGClassification
from .a20_semantic_segmentation import A20SemanticSegmentation
from .a21_vectorization import A21Vectorization
from .a22_topology_builder import A22TopologyBuilder
from .a23_dlg_symbolization import A23DLGSymbolization
from .a24_dlg_accuracy import A24DLGAccuracy

__all__ = [
    "A19DLGClassification",
    "A20SemanticSegmentation",
    "A21Vectorization",
    "A22TopologyBuilder",
    "A23DLGSymbolization",
    "A24DLGAccuracy",
]
