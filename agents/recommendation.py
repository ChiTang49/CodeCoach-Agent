"""
题目推荐 Agent
使用 Codeforces 数据源推荐算法题目
"""
from typing import List
from models import LearningPlan, ProblemInfo
from tools.codeforces import CodeforcesProblemTool


class RecommendationAgent:
    """题目推荐 Agent，通过 Codeforces API 提供题目列表"""

    def __init__(self):
        self.problem_tool = CodeforcesProblemTool()

    def recommend_problems(self, learning_plan: LearningPlan) -> List[ProblemInfo]:
        """
        推荐算法题目
        
        Args:
            learning_plan: 学习规划
            
        Returns:
            题目信息列表
        """
        tag = learning_plan.algorithm or ""
        difficulty = self._level_to_difficulty(learning_plan.level)

        try:
            problems = self.problem_tool.fetch_problems(tag=tag, difficulty=difficulty, limit=4)
        except RuntimeError as exc:
            print(f"获取 Codeforces 题目失败: {exc}")
            return [self._build_fallback_problem(learning_plan)]

        if not problems:
            return [self._build_fallback_problem(learning_plan)]

        return problems

    def _level_to_difficulty(self, level: str) -> str:
        if not level:
            return "medium"

        normalized = level.strip().lower()
        if "初" in normalized or "begin" in normalized or "入门" in normalized:
            return "easy"
        if "高" in normalized or "advanced" in normalized:
            return "hard"
        return "medium"

    def _build_fallback_problem(self, learning_plan: LearningPlan) -> ProblemInfo:
        return ProblemInfo(
            id=0,
            title="暂未找到合适的 Codeforces 题目",
            link="https://codeforces.com/problemset",
            description=f"请尝试在 Codeforces 上搜索标签 {learning_plan.algorithm}",
            difficulty=None,
            tags=[learning_plan.algorithm] if learning_plan.algorithm else [],
        )
