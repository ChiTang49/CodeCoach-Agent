"""
需求分析 Agent
负责将用户的自然语言输入转化为结构化的学习需求
"""
import json
from hello_agents import SimpleAgent, HelloAgentsLLM
from agents.prompts import REQUIREMENT_SYSTEM_PROMPT
from models import LearningPlan, LearningRequest


class RequirementAgent:
    """
    需求分析 Agent，将自然语言转化为 LearningPlan
    """
    
    def __init__(self):
        """初始化需求分析 Agent"""
        self.llm = HelloAgentsLLM()
        self.agent = SimpleAgent(
            name="RequirementAgent",
            llm=self.llm,
            system_prompt=REQUIREMENT_SYSTEM_PROMPT
        )
    
    def analyze(self, request: LearningRequest) -> LearningPlan:
        """
        分析用户的学习需求
        
        Args:
            request: 用户学习请求
            
        Returns:
            结构化的学习规划
        """
        # 构建分析提示
        prompt = f"""请分析以下用户的学习需求，并输出结构化的学习规划 JSON：

用户输入：{request.raw_input}

请输出符合以下格式的 JSON（不要包含任何其他文字）：
{{
    "algorithm": "算法类型",
    "level": "学习阶段（初级/中级/高级）",
    "learning_goal": "具体的学习目标",
    "weaknesses": ["潜在薄弱点1", "潜在薄弱点2"],
    "suggested_steps": ["学习步骤1", "学习步骤2", "学习步骤3"]
}}
"""
        
        # 调用 Agent
        response = self.agent.run(prompt)
        
        # 解析 JSON 响应
        try:
            # 提取 JSON 部分（处理可能的 markdown 格式）
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            # 解析并验证
            plan_data = json.loads(response)
            learning_plan = LearningPlan(**plan_data)
            return learning_plan
            
        except Exception as e:
            print(f"解析学习规划失败: {e}")
            print(f"原始响应: {response}")
            # 返回默认规划
            return LearningPlan(
                algorithm="未知算法",
                level="初级",
                learning_goal="需要进一步明确学习目标",
                weaknesses=["需求不够明确"],
                suggested_steps=["请提供更详细的学习需求"]
            )
