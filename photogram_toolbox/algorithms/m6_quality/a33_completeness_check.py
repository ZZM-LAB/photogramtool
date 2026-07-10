"""A33 成果完整性自动检查

检查项目成果文件是否齐全:
    1. 扫描工作目录
    2. 对照成果清单检查
    3. 生成缺失项报告
    4. 输出检查报告
"""
import os
import json
from photogram_toolbox.core import Algorithm, AlgoResult, AlgoContext, AlgoFeedback, REGISTRY


@REGISTRY.register
class A33CompletenessCheck(Algorithm):
    """A33 成果完整性自动检查"""

    @staticmethod
    def name() -> str:
        return "a33_completeness_check"

    @staticmethod
    def display_name() -> str:
        return "A33 成果完整性自动检查"

    @staticmethod
    def group() -> str:
        return "M6 质量评定"

    @staticmethod
    def group_id() -> str:
        return "m6"

    @staticmethod
    def short_help() -> str:
        return "检查成果文件是否齐全"

    @staticmethod
    def can_execute() -> bool:
        return True

    # 预期成果清单
    EXPECTED_DELIVERABLES = {
        "M1_空三": {
            "sparse": ["cameras.bin", "images.bin", "points3D.bin", "project.ini"],
            "dir": "sparse/0",
        },
        "M2_DEM": {
            "files": ["*_dem.tif", "*_dem_smoothed.tif", "*_contours.geojson"],
            "dir": ".",
        },
        "M3_DOM": {
            "files": ["*_ortho.tif", "*_mosaic_dom.tif"],
            "dir": ".",
        },
        "M4_DLG": {
            "files": ["*_classification.tif", "*_vectors.geojson"],
            "dir": ".",
        },
        "M5_航线": {
            "files": ["*_flightlines.geojson", "*_plan.json"],
            "dir": ".",
        },
    }

    def process(self, input_data, context: AlgoContext,
                feedback: AlgoFeedback) -> AlgoResult:
        """
        Args:
            input_data: 项目工作目录 (str)
        """
        work_dir = input_data
        if not work_dir or not os.path.isdir(work_dir):
            return AlgoResult(status=1, message=f"工作目录无效: {work_dir}")

        output_report = context.param("output_report",
                                       os.path.join(work_dir, "completeness_report.json"))

        feedback.push_info(f"检查目录: {work_dir}")
        feedback.set_progress(10)

        # 扫描目录
        all_files = []
        for root, dirs, files in os.walk(work_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), work_dir)
                all_files.append(rel)

        feedback.push_info(f"总文件数: {len(all_files)}")
        feedback.set_progress(30)

        # 检查各项成果
        results = {}
        missing_items = []
        found_items = []

        for module, spec in self.EXPECTED_DELIVERABLES.items():
            feedback.set_progress_text(f"检查 {module}...")
            module_dir = os.path.join(work_dir, spec.get("dir", "."))

            # 检查指定文件
            if "sparse" in spec:
                for fname in spec["sparse"]:
                    fpath = os.path.join(module_dir, fname)
                    exists = os.path.exists(fpath)
                    results[f"{module}/{fname}"] = exists
                    if exists:
                        found_items.append(f"{module}/{fname}")
                    else:
                        missing_items.append(f"{module}/{fname}")

            if "files" in spec:
                for pattern in spec["files"]:
                    # glob 匹配
                    import fnmatch
                    matched = [f for f in all_files if fnmatch.fnmatch(os.path.basename(f), pattern)]
                    exists = len(matched) > 0
                    results[f"{module}/{pattern}"] = {
                        "exists": exists,
                        "matched": matched[:3],  # 只显示前3个
                    }
                    if exists:
                        found_items.append(f"{module}/{pattern}")
                    else:
                        missing_items.append(f"{module}/{pattern}")

            feedback.set_progress(30 + int(
                (list(self.EXPECTED_DELIVERABLES.keys()).index(module) + 1) /
                len(self.EXPECTED_DELIVERABLES) * 60
            ))

        # 评分
        total = len(results)
        found = len(found_items)
        completeness = found / total if total > 0 else 0

        # 模块完整性
        module_status = {}
        for module in self.EXPECTED_DELIVERABLES:
            module_keys = [k for k in results if k.startswith(module)]
            module_found = sum(1 for k in module_keys
                             if isinstance(results[k], bool) and results[k]
                             or isinstance(results[k], dict) and results[k]["exists"])
            module_total = len(module_keys)
            module_status[module] = {
                "found": module_found,
                "total": module_total,
                "complete": module_found == module_total,
            }

        report = {
            "work_dir": work_dir,
            "total_files": len(all_files),
            "deliverables": results,
            "module_status": module_status,
            "summary": {
                "total_checks": total,
                "found": found,
                "missing": len(missing_items),
                "completeness": float(completeness),
                "missing_items": missing_items,
            }
        }

        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        feedback.set_progress(100)
        feedback.push_info(f"完整性: {found}/{total} ({completeness*100:.1f}%)")
        if missing_items:
            feedback.push_warning(f"缺失: {', '.join(missing_items[:5])}")

        return AlgoResult(
            status=0,
            message=f"完整性检查完成: {found}/{total} ({completeness*100:.1f}%)",
            outputs=[output_report],
            metadata=report["summary"]
        )
