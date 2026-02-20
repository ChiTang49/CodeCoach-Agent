from pydantic import BaseModel, Field
from typing import Optional, List


# 用户学习请求
class LearningRequest(BaseModel):
    raw_input: str                  # 用户原始输入
    timestamp: Optional[str] = None


# 学习规划模型
class LearningPlan(BaseModel):
    algorithm: str                  # 算法类型（如：动态规划、二分查找）
    level: str                      # 学习阶段（初级/中级/高级）
    learning_goal: str              # 学习目标
    weaknesses: List[str] = Field(default_factory=list)  # 潜在薄弱点
    suggested_steps: List[str] = Field(default_factory=list)  # 建议学习步骤


# 知识讲解模型
class KnowledgeItem(BaseModel):
    title: str                      # 知识点标题
    content: str                    # Markdown 格式的讲解内容
    examples: Optional[str] = None  # 示例说明
    common_mistakes: List[str] = Field(default_factory=list)  # 常见错误列表


# 算法题目信息
class ProblemInfo(BaseModel):
    id: int
    title: str
    link: str
    description: Optional[str] = None
    difficulty: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


# 用户代码提交
class SubmissionResult(BaseModel):
    problem_id: int
    status: str                     # AC / WA / TLE / RE
    runtime_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    error_message: Optional[str] = None


# 代码反馈结果
class CodeFeedback(BaseModel):
    summary: str                    # 总体评价
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    optimized_ideas: Optional[str] = None
