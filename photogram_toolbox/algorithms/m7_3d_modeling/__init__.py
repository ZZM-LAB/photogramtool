"""M7 三维建模模块 (A34-A38)

算法列表:
    A34 三维网格自动重建  - Poisson表面重建
    A35 纹理自动映射      - UV映射+顶点颜色
    A36 三维模型自动简化  - 边折叠(Quadric Decimation)
    A37 三维模型格式转换  - PLY/OBJ/STL/GLTF互转
    A38 三维模型质量评定  - 完整性/三角形质量/表面积体积
"""
from .a34_mesh_reconstruction import A34MeshReconstruction
from .a35_texture_mapping import A35TextureMapping
from .a36_mesh_simplification import A36MeshSimplification
from .a37_model_conversion import A37ModelConversion
from .a38_model_quality import A38ModelQualityAssessment

__all__ = [
    "A34MeshReconstruction",
    "A35TextureMapping",
    "A36MeshSimplification",
    "A37ModelConversion",
    "A38ModelQualityAssessment",
]
