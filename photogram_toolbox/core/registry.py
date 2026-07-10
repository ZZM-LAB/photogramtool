"""算法注册表 - 全局发现和检索算法

用法:
    from photogram_toolbox.core.registry import REGISTRY

    @REGISTRY.register
    class MyAlgo(Algorithm):
        ...

    algos = REGISTRY.algorithms()
    algo = REGISTRY.algorithm_by_id("my_algo")
"""
from typing import List, Optional
from .algorithm import Algorithm


class AlgorithmRegistry:
    """算法注册表（单例）"""

    def __init__(self):
        self._algos: dict = {}  # name -> class

    def register(self, algo_cls: type) -> type:
        """注册算法类（可作装饰器使用）

        用法:
            @REGISTRY.register
            class MyAlgo(Algorithm): ...

            或
            REGISTRY.register(MyAlgo)
        """
        name = algo_cls.name()
        if name in self._algos:
            raise ValueError(f"算法已注册: {name}")
        self._algos[name] = algo_cls
        return algo_cls

    def algorithms(self) -> List[type]:
        """返回所有已注册的算法类"""
        return list(self._algos.values())

    def algorithm_by_id(self, name: str) -> Optional[type]:
        """按名称查找算法类"""
        return self._algos.get(name)

    def algorithms_by_group(self, group_id: str) -> List[type]:
        """按模块分组过滤算法"""
        return [a for a in self._algos.values() if a.group_id() == group_id]

    def count(self) -> int:
        return len(self._algos)

    def clear(self) -> None:
        self._algos.clear()


# 全局单例
REGISTRY = AlgorithmRegistry()
