"""输出 Sink - 算法产物的统一输出接口

参考 QGIS Processing Framework 的 sink 概念：
算法不直接写文件到任意位置，而是通过 sink 输出，
由框架决定产物去向（文件/内存/透传）。
"""
import os
from typing import Optional


class AlgoSink:
    """输出 sink 基类"""

    def write(self, path: str, layer_name: str = "") -> None:
        """登记一个输出文件"""
        raise NotImplementedError

    @property
    def outputs(self) -> list:
        """所有已输出的文件路径"""
        raise NotImplementedError


class FileSink(AlgoSink):
    """文件输出 sink - 产物写入指定目录"""

    def __init__(self, output_dir: str):
        self._output_dir = output_dir
        self._outputs: list = []
        os.makedirs(output_dir, exist_ok=True)

    def write(self, path: str, layer_name: str = "") -> None:
        self._outputs.append(path)

    @property
    def outputs(self) -> list:
        return self._outputs


class MemorySink(AlgoSink):
    """内存输出 sink - 仅记录产物路径，不实际写盘"""

    def __init__(self):
        self._outputs: list = []

    def write(self, path: str, layer_name: str = "") -> None:
        self._outputs.append(path)

    @property
    def outputs(self) -> list:
        return self._outputs
