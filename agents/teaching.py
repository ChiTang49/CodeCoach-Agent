"""
教学 Agent
根据学习规划生成算法知识讲解内容
"""
import json
from typing import Optional
from hello_agents import SimpleAgent, HelloAgentsLLM
from agents.prompts import TEACHING_SYSTEM_PROMPT
from models import LearningPlan, KnowledgeItem


class TeachingAgent:
    """
    教学 Agent，生成结构化的算法讲解
    """
    
    def __init__(self):
        """初始化教学 Agent"""
        self.llm = HelloAgentsLLM()
        self.agent = SimpleAgent(
            name="TeachingAgent",
            llm=self.llm,
            system_prompt=TEACHING_SYSTEM_PROMPT
        )
    
    def generate_knowledge(self, learning_plan: LearningPlan, rag_context: str = "") -> KnowledgeItem:
        """
        生成知识讲解内容
        
        Args:
            learning_plan: 学习规划
            rag_context: RAG 检索到的参考知识（可选）
            
        Returns:
            知识讲解项
        """
        # 构建教学提示
        rag_section = ""
        if rag_context:
            rag_section = f"""

        【参考知识库资料】（请结合以下从知识库检索到的权威内容来生成讲解，确保准确性）：
{rag_context}
        【参考资料结束】
"""
        prompt = f"""请根据以下学习规划生成算法知识讲解：

        算法类型：{learning_plan.algorithm}
        学习阶段：{learning_plan.level}
        学习目标：{learning_plan.learning_goal}
        薄弱点：{', '.join(learning_plan.weaknesses)}
        学习步骤：{', '.join(learning_plan.suggested_steps)}{rag_section}

        请输出符合以下格式的 JSON（不要包含任何其他文字），并严格满足每个字段的详细要求：
        {{
            "title": "知识点标题",
            "content": "Markdown 格式的详细讲解，依次包含背景导入、核心概念拆解、算法步骤（用编号列表+伪代码块）、复杂度与优化、案例分析、进阶拓展等小节；总字数不少于 400 字，每个小节不少于两段说明",
            "examples": "补充性的示例说明（可选，可进一步扩展测试思路或可视化描述）",
            "common_mistakes": ["常见错误1", "常见错误2", "常见错误3"]
        }}

        注意：
        1. content 中使用 Markdown 格式，按小节使用二级标题（##）组织
        2. 只给出算法思路和关键步骤的伪代码，不要给出完整可运行的代码
        3. 每个编号步骤需要配合解释文本，避免只给伪代码
        4. common_mistakes 至少三条，描述具体原因与影响
        5. 输出必须是合法 JSON，不要在 JSON 外添加额外文字
        """
        
        # 调用 Agent
        response = self.agent.run(prompt)

        # 解析 JSON 响应
        try:
            json_block = self._extract_json_block(response)
            knowledge_data = json.loads(json_block)
            knowledge_item = KnowledgeItem(**knowledge_data)
            return knowledge_item

        except Exception as e:
            print(f"解析知识讲解失败: {e}")
            print(f"原始响应: {response}")
            # 返回详尽的默认内容
            return self._build_fallback_item(learning_plan)

    def _extract_json_block(self, response: str) -> str:
        """尝试从 LLM 输出中提取 JSON 字符串"""
        response = response.strip()
        if "```json" in response:
            return response.split("```json", 1)[1].split("```", 1)[0].strip()
        if "```" in response:
            return response.split("```", 1)[1].split("```", 1)[0].strip()

        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1 and end > start:
            return response[start:end + 1]

        raise ValueError("未找到有效的 JSON 内容")

    def _build_fallback_item(self, learning_plan: LearningPlan) -> KnowledgeItem:
        """当解析失败时，构造结构化的完整讲解"""
        algorithm = learning_plan.algorithm or "算法"
        steps = learning_plan.suggested_steps or ["梳理基础概念", "阅读经典案例", "通过练习巩固"]
        weaknesses = learning_plan.weaknesses or ["概念理解薄弱", "缺乏实战经验", "对复杂度分析不熟悉"]

        content = f"""## 背景导入
{algorithm} 是求解优化类问题时常用的策略，通常在面对需要快速决策的场景时表现出色。例如调度问题、资源分配及网络设计中，人们往往期望在有限时间内得到“足够好”的答案。理解 {algorithm} 的适用前提与局限性，能够帮助你判断何时采用该策略、何时需要转向动态规划或搜索枚举。

在真实项目中，{algorithm} 往往配合问题建模一并出现，需要先抽象出合适的数据结构，再设计出切实可行的贪心规则。因此学习过程中不仅要记住套路，更要能够解释贪心选择的合理性。

## 核心概念拆解
- **贪心选择性质**：每一步的局部最优选择可以扩展成全局最优。这一性质需要通过证明或反例验证，避免“想当然”。
- **最优子结构**：问题的最优解包含子问题的最优解。若子结构不具备最优性，应考虑动态规划或搜索。
- **可行解与最优解差异**：贪心算法始终保持解的可行性，但需特别关注是否被局部约束限制，从而无法覆盖全局最优。
- **策略设计步骤**：抽象状态→列举候选动作→验证贪心准则→尝试反例→给出证明或直观说明。

## 算法步骤
1. **建模与排序**：识别问题输入元素，决定排序或优先队列的关键字段。
2. **伪代码示意**：
```pseudo
function greedy_solve(items):
    sort(items, key=rule)
    answer = initialize_solution()
    for item in items:
        if is_feasible(answer, item):
            answer = incorporate(answer, item)
    return answer
```
3. **步骤说明**：排序阶段用于确保每次处理的候选满足贪心准则；循环中需实时判断可行性；更新操作既要维护解的正确性，也要考虑复杂度。
4. **复杂度分析**：排序通常贡献 O(n log n)，循环为 O(n)，若内部维护并查集或优先队列则再增加 log 因子。

## 复杂度与优化
- **时间复杂度**：最常见结构是排序 + 单次扫描，整体 O(n log n)。若能利用计数排序或特定数据结构，可降低至 O(n)。
- **空间复杂度**：依赖辅助结构，如优先队列、并查集等，通常在 O(n) 以内，但应警惕中间状态膨胀。
- **优化方向**：
  1. 通过预处理减少需考虑的候选，例如区间问题先合并冗余区间。
  2. 借助数学推导找到无需排序的闭式策略。
  3. 与动态规划结合，作为初始启发或剪枝条件。

## 案例分析
以“活动选择”问题为例：目标是最大化可安排的活动数量。贪心策略是按照结束时间排序，并在可行时选择活动。这样可以保证为后续活动保留更多时间窗口。证明过程强调：一旦选择了最早结束的活动，替换它并不会带来更多收益。

另一例是“霍夫曼编码”：每次取出频率最低的两个节点合并。此策略依赖优先队列维护候选，且能够证明任何最优前缀码都具备这一合并顺序。通过实例演算，可以帮助你体会贪心选择性质与最优子结构的配合。

## 进阶拓展
- 尝试解决“最大子段和”、“最小字典序排列”等问题，思考何种条件下贪心成立。
- 学习 Kruskal 与 Prim 算法在最小生成树问题中的应用，理解数据结构对效率的影响。
- 探索将贪心策略嵌入搜索或动态规划中的方法，例如 A* 算法的启发函数设计。
- 关注 Codeforces、AtCoder 上带有 greedy 标签的高分题，拓宽题型覆盖面。

## 练习建议
- {steps[0]}
- {steps[1]}
- {steps[2] if len(steps) > 2 else '在实践中总结经验并复盘错误'}

## 薄弱点提醒
- {weaknesses[0]}
- {weaknesses[1]}
- {weaknesses[2] if len(weaknesses) > 2 else '缺乏系统化复盘'}
"""

        common_mistakes = [
            "忽视贪心选择性质，未证明局部最优可推广至全局最优",
            "只关注排序规则，遗漏可行性检查导致解不可用",
            "未分析复杂度，导致在大数据场景下超时或内存不足",
        ]

        return KnowledgeItem(
            title=f"{algorithm} 系统讲解",
            content=content,
            examples="尝试使用区间调度与零钱兑换两个问题，分步骤验证贪心选择的充分性。",
            common_mistakes=common_mistakes,
        )
