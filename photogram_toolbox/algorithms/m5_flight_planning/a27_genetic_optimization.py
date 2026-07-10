"""A27 遗传算法航线优化

使用遗传算法优化航线顺序,最小化总飞行距离:
    1. 将航线排序视为TSP问题
    2. 种群初始化(随机排列)
    3. 选择/交叉/变异
    4. 迭代优化
    5. 输出最优航线顺序
"""
import os
import json
import numpy as np
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A27GeneticOptimization(Algorithm):
    """A27 遗传算法航线优化"""

    @staticmethod
    def name() -> str:
        return "a27_genetic_optimization"

    @staticmethod
    def display_name() -> str:
        return "A27 遗传算法航线优化"

    @staticmethod
    def group() -> str:
        return "M5 航线规划"

    @staticmethod
    def group_id() -> str:
        return "m5"

    @staticmethod
    def short_help() -> str:
        return "遗传算法优化航线顺序,最小化总飞行距离"

    @staticmethod
    def can_execute() -> bool:
        return True

    def _total_distance(self, order, start_points):
        """计算给定顺序的总飞行距离"""
        total = 0
        prev = np.array([0, 0])  # 起点(原点)
        for idx in order:
            curr = start_points[idx]
            total += np.sum((curr - prev) ** 2) ** 0.5
            prev = curr
        return total

    def _crossover(self, parent1, parent2):
        """顺序交叉(OX)"""
        n = len(parent1)
        start, end = sorted(np.random.choice(n, 2, replace=False))
        child = [-1] * n
        child[start:end] = parent1[start:end]

        p2_remaining = [x for x in parent2 if x not in child[start:end]]
        j = 0
        for i in range(n):
            if child[i] == -1:
                child[i] = p2_remaining[j]
                j += 1
        return child

    def _mutate(self, individual, rate=0.1):
        """交换变异"""
        if np.random.random() < rate:
            i, j = np.random.choice(len(individual), 2, replace=False)
            individual[i], individual[j] = individual[j], individual[i]
        return individual

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 航线GeoJSON (str)
        """
        flight_path = input_data
        if not flight_path or not os.path.exists(flight_path):
            return AlgoResult(status=1, message=f"航线文件无效: {flight_path}")

        output_path = context.param("output_path",
                                     flight_path.replace(".geojson", "_optimized.geojson"))
        population_size = context.param("population_size", 50)
        n_generations = context.param("n_generations", 100)
        mutation_rate = context.param("mutation_rate", 0.1)

        feedback.push_info(f"种群: {population_size}, 代数: {n_generations}")

        # 1. 读取航线
        feedback.set_progress_text("读取航线...")
        with open(flight_path, 'r', encoding='utf-8') as f:
            geojson = json.load(f)

        # 提取每条航线的起点
        line_starts = {}
        for feat in geojson["features"]:
            if feat["geometry"]["type"] == "LineString":
                coords = feat["geometry"]["coordinates"]
                line_id = feat["properties"]["line_id"]
                line_starts[line_id] = np.array(coords[0])

        line_ids = sorted(line_starts.keys())
        n_lines = len(line_ids)
        if n_lines < 2:
            return AlgoResult(status=1, message="航线数不足")

        start_points = np.array([line_starts[i] for i in line_ids])
        feedback.push_info(f"航线数: {n_lines}")
        feedback.set_progress(20)

        # 2. 遗传算法
        feedback.set_progress_text("执行遗传算法优化...")

        # 初始种群
        population = [np.random.permutation(n_lines) for _ in range(population_size)]

        best_order = None
        best_distance = float('inf')
        history = []

        for gen in range(n_generations):
            if feedback.is_canceled():
                return AlgoResult(status=2, message="用户取消")

            # 评估适应度
            distances = [self._total_distance(ind, start_points) for ind in population]

            # 记录最优
            gen_best_idx = np.argmin(distances)
            if distances[gen_best_idx] < best_distance:
                best_distance = distances[gen_best_idx]
                best_order = population[gen_best_idx].copy()

            history.append(best_distance)

            # 选择(锦标赛)
            new_population = [best_order.copy()]  # 精英保留
            while len(new_population) < population_size:
                # 锦标赛选择
                k = min(3, population_size)
                candidates = np.random.choice(population_size, k, replace=False)
                winner = candidates[np.argmin([distances[c] for c in candidates])]

                # 交叉
                if len(new_population) > 0:
                    parent2_idx = np.random.choice(population_size)
                    child = self._crossover(population[winner], population[parent2_idx])
                else:
                    child = population[winner].copy()

                # 变异
                child = self._mutate(child, mutation_rate)
                new_population.append(child)

            population = new_population

            if gen % max(1, n_generations // 10) == 0:
                feedback.set_progress(20 + int(gen / n_generations * 70))
                feedback.push_info(f"  Gen {gen}: best={best_distance:.1f}m")

        feedback.set_progress(90)

        # 3. 重新排列航线
        optimized_order = [line_ids[i] for i in best_order]
        feedback.push_info(f"最优顺序: {optimized_order}")
        feedback.push_info(f"最优距离: {best_distance:.1f}m")

        # 重新生成GeoJSON(按优化顺序)
        line_features = {}
        point_features = []
        for feat in geojson["features"]:
            if feat["geometry"]["type"] == "LineString":
                lid = feat["properties"]["line_id"]
                line_features[lid] = feat
            else:
                point_features.append(feat)

        ordered_features = []
        for lid in optimized_order:
            if lid in line_features:
                ordered_features.append(line_features[lid])

        ordered_features.extend(point_features)

        result_geojson = {
            "type": "FeatureCollection",
            "features": ordered_features,
            "metadata": {
                "optimized_order": optimized_order,
                "total_distance_m": float(best_distance),
                "generations": n_generations,
            }
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_geojson, f, ensure_ascii=False)

        feedback.set_progress(100)
        feedback.push_info(f"优化完成: {output_path}")

        return AlgoResult(
            status=0,
            message=f"遗传算法优化完成, 总距离 {best_distance:.1f}m",
            outputs=[output_path],
            metadata={
                "output_path": output_path,
                "optimized_order": optimized_order,
                "total_distance_m": float(best_distance),
                "generations": n_generations,
            }
        )
