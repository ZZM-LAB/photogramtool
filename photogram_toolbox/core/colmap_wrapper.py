"""COLMAP Python API 封装 - SfM 流程的统一工具层

将 pycolmap 的底层 API 封装为摄影测量语义的高级接口,
供 A01-A06 算法调用,避免重复代码。

核心流程:
    import_images → extract_features → match_exhaustive
    → incremental_mapping → bundle_adjustment → undistort_images
"""
import os
from pathlib import Path
from typing import Optional


def ensure_dir(path: str) -> str:
    """确保目录存在,返回路径字符串"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


def database_path(work_dir: str) -> str:
    """数据库文件路径"""
    return os.path.join(work_dir, "database.db")


def create_database(work_dir: str):
    """创建 COLMAP 数据库"""
    import pycolmap
    db = database_path(work_dir)
    if os.path.exists(db):
        os.remove(db)
    pycolmap.Database(db)
    return db


def import_images(image_dir: str, work_dir: str,
                  camera_model: str = "SIMPLE_RADIAL",
                  single_camera: bool = True):
    """导入影像到数据库

    Args:
        image_dir: 影像目录
        work_dir: 工作目录(含 database.db)
        camera_model: 相机模型 SIMPLE_RADIAL/PINHOLE/RADIAL等
        single_camera: True=所有影像共用同一相机

    Returns:
        pycolmap.ImageReaderOptions
    """
    import pycolmap

    opts = pycolmap.ImageReaderOptions()
    opts.camera_model = camera_model
    opts.single_camera = single_camera
    pycolmap.import_images(database_path(work_dir), image_dir, opts)
    return opts


def extract_features(work_dir: str, use_gpu: bool = False):
    """SIFT 特征提取

    Args:
        work_dir: 工作目录
        use_gpu: 是否用GPU(pycolmap CPU版只能False)
    """
    import pycolmap

    opts = pycolmap.SiftExtractionOptions()
    opts.use_gpu = use_gpu
    pycolmap.extract_features(database_path(work_dir), opts)
    return opts


def match_exhaustive(work_dir: str, use_gpu: bool = False):
    """全量特征匹配(影像<500张用此方法)"""
    import pycolmap

    opts = pycolmap.SiftMatchingOptions()
    opts.use_gpu = use_gpu
    pycolmap.match_exhaustive(database_path(work_dir), opts)
    return opts


def incremental_mapping(work_dir: str, image_dir: str,
                        sparse_dir: Optional[str] = None) -> str:
    """增量式 SfM 重建

    Args:
        work_dir: 工作目录(含 database.db)
        image_dir: 影像目录
        sparse_dir: 输出目录,默认 work_dir/sparse

    Returns:
        稀疏重建输出目录
    """
    import pycolmap

    if sparse_dir is None:
        sparse_dir = os.path.join(work_dir, "sparse")
    ensure_dir(sparse_dir)

    mapper_opts = pycolmap.IncrementalPipelineOptions()
    maps = pycolmap.incremental_mapping(
        database_path(work_dir), image_dir, sparse_dir, mapper_opts
    )
    return sparse_dir


def bundle_adjustment(sparse_dir: str):
    """光束平差精修"""
    import pycolmap

    recon = pycolmap.Reconstruction(sparse_dir)
    opts = pycolmap.BundleAdjustmentOptions()
    ba = pycolmap.BundleAdjuster(opts)
    ba.solve(recon)
    recon.write(sparse_dir)
    return recon


def undistort_images(work_dir: str, image_dir: str,
                     sparse_dir: str, dense_dir: Optional[str] = None) -> str:
    """影像去畸变(为稠密重建做准备)

    Args:
        work_dir: 工作目录
        image_dir: 原始影像目录
        sparse_dir: 稀疏重建结果目录
        dense_dir: 输出目录,默认 work_dir/dense

    Returns:
        稠密重建工作目录
    """
    import pycolmap

    if dense_dir is None:
        dense_dir = os.path.join(work_dir, "dense")
    ensure_dir(dense_dir)

    pycolmap.undistort_images(
        output_path=dense_dir,
        input_path=sparse_dir,
        image_path=image_dir,
    )
    return dense_dir


def align_to_gps(sparse_dir: str, gps_file: str):
    """将重建结果对齐到GPS/控制点坐标

    Args:
        sparse_dir: 稀疏重建目录
        gps_file: 控制点文件路径
    """
    import pycolmap

    recon = pycolmap.Reconstruction(sparse_dir)
    # 读取控制点(image_name, x, y, z)
    locations = {}
    with open(gps_file, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                locations[parts[0]] = [float(parts[1]),
                                       float(parts[2]),
                                       float(parts[3])]
    pycolmap.align_reconstruction_to_locations(recon, locations)
    recon.write(sparse_dir)
    return recon
