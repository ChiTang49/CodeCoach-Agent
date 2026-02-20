"""
代码评审 Agent
分析用户提交的代码并提供改进建议
"""
import json
from hello_agents import SimpleAgent, HelloAgentsLLM
from agents.prompts import REVIEW_SYSTEM_PROMPT
from models import ProblemInfo, SubmissionResult, CodeFeedback


class ReviewAgent:
    """
    代码评审 Agent，提供代码改进建议
    """
    
    def __init__(self):
        """初始化评审 Agent"""
        self.llm = HelloAgentsLLM()
        self.agent = SimpleAgent(
            name="ReviewAgent",
            llm=self.llm,
            system_prompt=REVIEW_SYSTEM_PROMPT
        )
    
    def review_code(
        self,
        problem: ProblemInfo,
        user_code: str,
        result: SubmissionResult
    ) -> CodeFeedback:
        """
        评审用户代码
        
        Args:
            problem: 题目信息
            user_code: 用户提交的代码
            result: 评测结果
            
        Returns:
            代码反馈
        """
        # 构建评审提示
        prompt = f"""请评审以下代码并提供改进建议：

题目信息：
- 标题：{problem.title}
- 难度：{problem.difficulty}
- 标签：{', '.join(problem.tags)}

用户代码：
```
{user_code}
```

评测结果：
- 状态：{result.status}
- 运行时间：{result.runtime_ms} ms
- 内存：{result.memory_kb} KB
- 错误信息：{result.error_message or '无'}

请输出符合以下格式的 JSON（不要包含任何其他文字）：
{{
    "summary": "总体评价",
    "issues": ["问题1", "问题2"],
    "suggestions": ["建议1", "建议2"],
    "optimized_ideas": "优化思路说明（可选）"
}}

注意：
1. 不要直接给出最终代码
2. 通过问题引导用户思考
3. 提供算法思路层面的建议
4. 鼓励用户自己改进代码
"""
        
        # 调用 Agent
        response = self.agent.run(prompt)
        
        # 解析 JSON 响应
        try:
            # 提取 JSON 部分
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            # 解析并验证
            feedback_data = json.loads(response)
            code_feedback = CodeFeedback(**feedback_data)
            return code_feedback
            
        except Exception as e:
            print(f"解析代码反馈失败: {e}")
            print(f"原始响应: {response}")
            # 返回默认反馈
            return CodeFeedback(
                summary=f"代码评测结果：{result.status}",
                issues=["评审系统暂时无法解析反馈，请稍后重试"],
                suggestions=["建议检查代码逻辑和边界条件"]
            )
