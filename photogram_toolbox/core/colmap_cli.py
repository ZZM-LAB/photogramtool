"""COLMAP 命令行封装 - 调用 COLMAP 预编译二进制执行 MVS 流程

pycolmap (CPU版) 不支持 patch_match_stereo,需调用 COLMAP CUDA 二进制。
路径: D:\\Tools\\COLMAP\\bin\\colmap.exe
"""
import os
import subprocess
import shutil
from pathlib import Path
from typing import Optional


def find_colmap() -> str:
    """查找 COLMAP 可执行文件路径"""
    # 1. 系统 PATH
    exe = shutil.which("colmap")
    if exe:
        return exe
    # 2. 默认安装位置
    default = r"D:\Tools\COLMAP\bin\colmap.exe"
    if os.path.exists(default):
        return default
    raise FileNotFoundError(
        "未找到 COLMAP。请安装 COLMAP 并加入 PATH,或放到 D:\\Tools\\COLMAP\\bin\\"
    )


def run_colmap(args: list, cwd: Optional[str] = None,
               timeout: int = 3600) -> subprocess.CompletedProcess:
    """执行 COLMAP 命令

    Args:
        args: 命令参数列表,如 ['patch_match_stereo', '--workspace_path', '.']
        cwd: 工作目录
        timeout: 超时秒数

    Returns:
        CompletedProcess
    """
    exe = find_colmap()
    cmd = [exe] + args
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        encoding="utf-8", errors="replace"
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"COLMAP 命令失败 (exit {result.returncode}):\n"
            f"命令: {' '.join(cmd)}\n"
            f"STDERR: {result.stderr[-1000:]}"
        )
    return result


def patch_match_stereo(workspace_path: str, workspace_format: str = "COLMAP"):
    """MVS 稠密立体匹配 (Patch Match Stereo)

    输入: image_undistorter 的输出 (workspace_path)
    输出: workspace_path/stereo/{depth_maps,normal_maps}
    """
    run_colmap([
        "patch_match_stereo",
        "--workspace_path", workspace_path,
        "--workspace_format", workspace_format,
    ])


def stereo_fusion(workspace_path: str, output_path: str,
                  workspace_format: str = "COLMAP"):
    """立体融合 - 将深度图融合为稠密点云

    输出: output_path (PLY 文件)
    """
    run_colmap([
        "stereo_fusion",
        "--workspace_path", workspace_path,
        "--workspace_format", workspace_format,
        "--output_path", output_path,
    ])


def poisson_mesher(input_ply: str, output_ply: str):
    """Poisson 网格重建"""
    run_colmap([
        "poisson_mesher",
        "--input_path", input_ply,
        "--output_path", output_ply,
    ])


def delaunay_mesher(input_path: str, output_path: str):
    """Delaunay 网格重建"""
    run_colmap([
        "delaunay_mesher",
        "--input_path", input_path,
        "--output_path", output_path,
    ])
