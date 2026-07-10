"""流水线编排 - 串联多个算法形成端到端处理流程

支持:
- 线性串联: A -> B -> C
- 产物传递: 上一个算法的 outputs 作为下一个的 input
- 进度聚合: 各算法进度按权重汇总
- 失败中断: 任一步骤失败则停止
"""
from typing import List, Optional
from .algorithm import Algorithm, AlgoResult, STATUS_OK
from .context import AlgoContext
from .feedback import AlgoFeedback


class PipelineStep:
    """流水线中的一个步骤"""

    def __init__(self, algo: Algorithm, name: str = "",
                 input_mapper=None, param_override: dict = None):
        self.algo = algo
        self.name = name or algo.name()
        self.input_mapper = input_mapper  # func(prev_result) -> input_data
        self.param_override = param_override or {}

    def resolve_input(self, prev_result: Optional[AlgoResult]):
        if self.input_mapper:
            return self.input_mapper(prev_result)
        if prev_result and prev_result.outputs:
            return prev_result.outputs[0]  # 默认取第一个产物
        return None


class Pipeline:
    """处理流水线

    用法:
        pipe = Pipeline("dem_production")
        pipe.add(A07MVS())
        pipe.add(A09CSFFilter())
        pipe.add(A10IDW())
        result = pipe.run(image_dir, context, feedback)
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._steps: List[PipelineStep] = []

    def add(self, algo: Algorithm, name: str = "",
            input_mapper=None, param_override: dict = None) -> "Pipeline":
        """添加步骤"""
        self._steps.append(PipelineStep(algo, name, input_mapper, param_override))
        return self

    def run(self, initial_input, context: AlgoContext,
            feedback: AlgoFeedback) -> AlgoResult:
        """执行整条流水线

        每个步骤的 outputs[0] 自动作为下一步的输入（可用 input_mapper 自定义）
        """
        total = len(self._steps)
        prev_result: Optional[AlgoResult] = None
        current_input = initial_input

        for i, step in enumerate(self._steps):
            if feedback.is_canceled():
                return AlgoResult(status=2, message="流水线被取消")

            # 进度分配: 每步占 total 的等分
            base_pct = int(i / total * 100)
            feedback.set_progress(base_pct)
            feedback.set_progress_text(f"[{i+1}/{total}] {step.name}")

            # 参数覆盖
            ctx = context
            if step.param_override:
                import copy
                ctx = copy.copy(context)
                ctx.parameters.update(step.param_override)

            # 解析输入
            current_input = step.resolve_input(prev_result)

            # 执行
            result = step.algo.process(current_input, ctx, feedback)
            if not result.success:
                result.message = f"步骤 {step.name} 失败: {result.message}"
                return result

            prev_result = result

        feedback.set_progress(100)
        return prev_result or AlgoResult(status=0, message="流水线无步骤")
