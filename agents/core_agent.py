"""
核心对话 Agent
基于 hello-agents 框架实现，具备记忆能力的主 Agent
"""
import os
import json
import re
import time
from typing import List, Optional
from dotenv import load_dotenv
from hello_agents import SimpleAgent, HelloAgentsLLM, ToolRegistry
from agents.prompts import CORE_SYSTEM_PROMPT
from agents.requirement import RequirementAgent
from agents.teaching import TeachingAgent
from agents.recommendation import RecommendationAgent
from models import LearningRequest, ProblemInfo
from tools.simple_memory import SimpleMemoryManager, format_search_results
from tools.codeforces import CodeforcesProblemFetcher

# 先加载环境变量
load_dotenv()

# RAG 模块（延迟导入，避免启动时强制依赖）
try:
    from rag.service import RAGService
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False


class CoreAgent:
    """
    核心对话 Agent，负责协调各个子 Agent 并维护记忆
    """
    
    def __init__(self, user_id: str = "default_user"):
        """
        初始化核心 Agent
        
        Args:
            user_id: 用户唯一标识
        """
        self.user_id = user_id
        
        # 创建 LLM 实例
        self.llm = HelloAgentsLLM()
        
        # 创建 Agent
        self.agent = SimpleAgent(
            name="CodeCoach-CoreAgent",
            llm=self.llm,
            system_prompt=CORE_SYSTEM_PROMPT
        )
        
        # 创建工具注册表
        tool_registry = ToolRegistry()

        # 初始化子 Agent
        self.requirement_agent = RequirementAgent()
        self.teaching_agent = TeachingAgent()
        self.recommendation_agent = RecommendationAgent()
        
        # 初始化简化的记忆管理器
        try:
            self.memory_manager = SimpleMemoryManager(user_id=user_id)
            self.has_memory = True
            print(f"✅ 记忆功能已启用（Qdrant 向量搜索）")
        except Exception as e:
            print(f"⚠️ 记忆功能初始化失败: {e}")
            self.memory_manager = None
            self.has_memory = False
        
        # 初始化 RAG 服务
        self.rag_service = None
        if RAG_AVAILABLE:
            try:
                self.rag_service = RAGService()
                if self.rag_service.is_ready():
                    print("✅ RAG 知识库已就绪")
                else:
                    print("⚠️ RAG 服务已加载，但知识库尚未索引（请运行 python rag_ingest.py）")
            except Exception as e:
                print(f"⚠️ RAG 服务初始化失败: {e}")
                self.rag_service = None
        
        # 为 Agent 配置工具
        self.agent.tool_registry = tool_registry
        
    def run(self, user_message: str) -> str:
        """
        处理用户消息
        
        Args:
            user_message: 用户输入的消息（可能包含上下文信息）
            
        Returns:
            Agent 的响应
        """
        t_start = time.time()
        
        # 检测是否包含Codeforces题目链接
        cf_problem = self._extract_codeforces_problem(user_message)
        
        # ---- 提取用于 RAG 检索的原始查询 ----
        if "[当前消息]:" in user_message:
            rag_query = user_message.split("[当前消息]:")[-1].strip()
        else:
            rag_query = user_message
        
        rag_ready = self.rag_service and self.rag_service.is_ready()
        is_learning = self._is_learning_request(user_message)
        is_knowledge = self._is_knowledge_query(user_message)
        
        # 仅知识型非学习型查询走完整 RAG pipeline（含 LLM 答案生成）
        if not is_learning and is_knowledge and rag_ready:
            response = self._handle_rag_query(user_message)
        else:
            # ---- 其他路径：轻量 RAG 上下文检索 ----
            rag_context = ""
            rag_timing: dict = {}
            if rag_ready:
                try:
                    t_rag = time.time()
                    rag_context, rag_timing = self.rag_service.retrieve_context(
                        rag_query, top_k_retrieve=8, top_k_rerank=3,
                        use_query_rewrite=True
                    )
                    rag_timing["_elapsed"] = round(time.time() - t_rag, 2)
                except Exception as e:
                    print(f"RAG 上下文检索失败: {e}")
            
            if is_learning:
                response = self._handle_learning_request(user_message, cf_problem, rag_context, rag_timing)
            else:
                # 如果有题目信息，添加到消息中
                if cf_problem:
                    problem_info = self._format_problem_info(cf_problem)
                    if "[题目信息]" not in user_message:
                        user_message = f"[题目信息]:\n{problem_info}\n\n{user_message}"
                
                # 注入 RAG 上下文到普通 Agent 对话
                if rag_context:
                    user_message = f"[知识库参考资料]:\n{rag_context}\n[参考资料结束]\n\n{user_message}"
                
                # 调用 Agent 处理
                t_llm = time.time()
                response = self.agent.run(user_message)
                llm_time = round(time.time() - t_llm, 2)
                # 格式化耗时
                parts = []
                if rag_timing.get("_elapsed"):
                    parts.append(f"RAG检索: {rag_timing['_elapsed']}s")
                parts.append(f"LLM生成: {llm_time}s")
                response += f"\n\n---\n> ⏱ {' | '.join(parts)}"
        
        total_time = round(time.time() - t_start, 2)
        
        # 获取记忆搜索耗时（由 server.py 设置）
        mem_time = getattr(self, '_memory_search_time', 0.0)
        mem_part = f"记忆搜索: {mem_time}s | " if mem_time > 0 else ""
        
        # 如果响应中已有模块详细耗时，将记忆搜索和总时长追加到末尾
        if "\n\n---\n> ⏱" in response:
            # 在 ⏱ 后插入记忆搜索耗时，追加总时长
            if mem_part:
                response = response.replace("\n\n---\n> ⏱ ", f"\n\n---\n> ⏱ {mem_part}")
            response += f" | 响应总时长：**{total_time}s**"
        else:
            # 无模块耗时（理论上不应该到这里了）
            response += f"\n\n---\n> ⏱ {mem_part}响应总时长：**{total_time}s**"
        
        # 保存关键信息到长期记忆
        if self.has_memory:
            # 从消息中提取原始用户输入（去除上下文标记）
            if "[当前消息]:" in user_message:
                original_message = user_message.split("[当前消息]:")[-1].strip()
            else:
                original_message = user_message
            self.save_to_memory(original_message, response)
        
        return response
    
    def _extract_codeforces_problem(self, user_message: str) -> Optional[dict]:
        """
        检测并提取Codeforces题目信息
        """
        # 检测Codeforces链接
        if 'codeforces.com' in user_message.lower():
            problem_info = CodeforcesProblemFetcher.get_problem_from_url(user_message)
            if problem_info:
                return problem_info
        return None
    
    def _format_problem_info(self, problem: dict) -> str:
        """
        格式化题目信息为Markdown
        """
        parts = []
        
        if 'title' in problem:
            parts.append(f"**题目**: {problem['title']}")
        
        if 'time_limit' in problem or 'memory_limit' in problem:
            limits = []
            if 'time_limit' in problem:
                limits.append(f"时间: {problem['time_limit']}")
            if 'memory_limit' in problem:
                limits.append(f"内存: {problem['memory_limit']}")
            parts.append(f"**限制**: {', '.join(limits)}")
        
        if 'statement' in problem:
            parts.append(f"**题目描述**: {problem['statement']}")
        
        if 'input' in problem:
            parts.append(f"**输入格式**: {problem['input']}")
        
        if 'output' in problem:
            parts.append(f"**输出格式**: {problem['output']}")
        
        parts.append(f"**链接**: {problem.get('link', 'N/A')}")
        
        return "\n\n".join(parts)

    def _is_learning_request(self, user_message: str) -> bool:
        """判断是否为学习需求请求"""
        keywords = [
            "学习",
            "想学",
            "了解",
            "掌握",
            "算法",
            "数据结构",
            "怎么学",
            "教程",
            "入门",
            "题目",
            "练习",
        ]
        return any(keyword in user_message for keyword in keywords)

    def _is_knowledge_query(self, user_message: str) -> bool:
        """判断是否为算法知识查询（适合 RAG 回答）"""
        # 提取原始消息（去除上下文标记）
        if "[当前消息]:" in user_message:
            msg = user_message.split("[当前消息]:")[-1].strip()
        else:
            msg = user_message
        
        knowledge_keywords = [
            "什么是", "是什么", "原理", "概念", "定义", "区别",
            "怎么实现", "如何实现", "时间复杂度", "空间复杂度",
            "讲解", "解释", "介绍", "说明",
            "DP", "BFS", "DFS", "贪心", "分治", "排序", "搜索",
            "动态规划", "最短路", "最小生成树", "拓扑排序", "二分",
            "线段树", "树状数组", "并查集", "哈希", "KMP", "AC自动机",
            "图论", "数论", "组合数学", "博弈论",
        ]
        return any(kw in msg for kw in knowledge_keywords)

    def _handle_rag_query(self, user_message: str) -> str:
        """使用 RAG 知识库回答算法知识问题"""
        # 提取原始消息
        if "[当前消息]:" in user_message:
            query = user_message.split("[当前消息]:")[-1].strip()
        else:
            query = user_message
        
        try:
            result = self.rag_service.answer_with_evidence(query)
            answer = result.answer
            
            # 格式化各模块耗时
            if result.timing:
                t = result.timing
                timing_parts = []
                if "query_rewrite" in t:
                    timing_parts.append(f"Query Rewrite: {t['query_rewrite']}s")
                if "retrieval_rrf" in t:
                    timing_parts.append(f"检索+RRF融合: {t['retrieval_rrf']}s")
                if "reranking" in t:
                    timing_parts.append(f"Re-Ranking: {t['reranking']}s")
                if "llm_generation" in t:
                    timing_parts.append(f"LLM生成: {t['llm_generation']}s")
                
                timing_str = " | ".join(timing_parts)
                answer += f"\n\n---\n> ⏱ {timing_str}"
            
            return answer
        except Exception as e:
            print(f"RAG 查询失败: {e}，回退到普通 Agent")
            return self.agent.run(user_message)

    def _needs_problem_recommendation(self, user_message: str) -> bool:
        """判断用户是否需要题目推荐"""
        # 明确要求题目推荐的关键词
        recommend_keywords = [
            "推荐题目", "推荐题", "练习题", "做题", "刷题",
            "题目", "练习", "实践", "巩固", "习题"
        ]
        
        # 只想了解概念的关键词（不一定需要题目）
        concept_only_keywords = [
            "是什么", "介绍一下", "讲解一下", "什么是",
            "解释", "概念"
        ]
        
        # 如果明确要求题目，返回True
        if any(keyword in user_message for keyword in recommend_keywords):
            return True
        
        # 如果只是概念性问题且没有提到实践，返回False
        if any(keyword in user_message for keyword in concept_only_keywords):
            if not any(k in user_message for k in ["怎么用", "如何", "学习", "掌握", "应用"]):
                return False
        
        # 默认：学习性请求推荐题目
        learning_keywords = ["学习", "想学", "掌握", "怎么学", "入门"]
        return any(keyword in user_message for keyword in learning_keywords)

    def _handle_learning_request(self, user_message: str, cf_problem: Optional[dict] = None,
                                    rag_context: str = "", rag_timing: dict = None) -> str:
        """使用需求分析 + 教学 + 题目推荐工具生成结构化回复（RAG 增强）"""
        from concurrent.futures import ThreadPoolExecutor, Future
        timing_parts = []
        rag_timing = rag_timing or {}

        # 如果提供了Codeforces题目，提取题解思路而非完整教学
        if cf_problem:
            return self._handle_problem_solution_request(user_message, cf_problem, rag_context, rag_timing)

        if rag_timing.get("_elapsed"):
            timing_parts.append(f"RAG检索: {rag_timing['_elapsed']}s")
        
        t0 = time.time()
        request = LearningRequest(raw_input=user_message)
        learning_plan = self.requirement_agent.analyze(request)
        timing_parts.append(f"需求分析: {round(time.time() - t0, 2)}s")

        t0 = time.time()
        # 并行：教学生成 + 题目推荐（互不依赖）
        needs_recommendations = self._needs_problem_recommendation(user_message)
        with ThreadPoolExecutor(max_workers=2) as executor:
            teach_future = executor.submit(
                self.teaching_agent.generate_knowledge, learning_plan, rag_context
            )
            rec_future: Future = None
            if needs_recommendations:
                rec_future = executor.submit(
                    self.recommendation_agent.recommend_problems, learning_plan
                )
            knowledge_item = teach_future.result()
            timing_parts.append(f"教学生成: {round(time.time() - t0, 2)}s")
        
        sections: List[str] = []
        title = knowledge_item.title or f"{learning_plan.algorithm} 学习指导"
        sections.append(f"# {title}")

        if knowledge_item.content:
            sections.append(knowledge_item.content)

        if knowledge_item.examples:
            sections.append("## 示例补充\n" + knowledge_item.examples)

        if knowledge_item.common_mistakes:
            mistakes = "\n".join(f"- {item}" for item in knowledge_item.common_mistakes)
            sections.append("## 常见错误与误区\n" + mistakes)

        # 条件性地添加题目推荐（已并行执行）
        if needs_recommendations and rec_future is not None:
            problems = rec_future.result()
            timing_parts.append(f"题目推荐: ✓")
            sections.append(self._format_recommendations(problems))
        
        # 追加各模块耗时
        timing_str = " | ".join(timing_parts)
        sections.append(f"\n---\n> ⏱ {timing_str}")

        return "\n\n".join(sections).strip()

    def _format_recommendations(self, problems: List[ProblemInfo]) -> str:
        """将题目推荐格式化为 Markdown"""
        if not problems:
            return "## 推荐练习 🎯\n暂未找到合适的题目，请稍后再试。"

        lines = ["## 推荐练习 🎯", "为了巩固学习，推荐以下题目：", ""]
        for idx, problem in enumerate(problems[:3], start=1):
            difficulty = problem.difficulty or "未知"
            tags = ", ".join(problem.tags) if problem.tags else "综合"
            lines.append(f"{idx}. **{problem.title}**（难度：{difficulty}）")
            lines.append("   - 平台：Codeforces")
            lines.append(f"   - 题号：{problem.id}")
            lines.append(f"   - 链接：{problem.link}")
            lines.append(f"   - 考察点：{tags}")
            lines.append("")

        return "\n".join(lines).strip()
    
    def _handle_problem_solution_request(self, user_message: str, cf_problem: dict,
                                          rag_context: str = "", rag_timing: dict = None) -> str:
        """
        处理具体题目的解题请求（RAG 增强）
        """
        rag_timing = rag_timing or {}
        # 构建包含题目信息的提示
        problem_context = f"""你现在需要分析一道具体的Codeforces题目，请严格按照以下要求回复：

# {cf_problem.get('title', '题目')}

## 📋 题目信息
- **题号**: {cf_problem.get('contest_id', 'N/A')}{cf_problem.get('problem_index', '')}
- **链接**: {cf_problem.get('link', 'N/A')}
- **时间限制**: {cf_problem.get('time_limit', 'N/A')}
- **内存限制**: {cf_problem.get('memory_limit', 'N/A')}

## 📝 题目描述
{cf_problem.get('statement', '题目描述获取失败')}

## 📥 输入格式
{cf_problem.get('input', 'N/A')}

## 📤 输出格式
{cf_problem.get('output', 'N/A')}

---

**用户问题**: {user_message}

**你的任务**：请为这道题目提供详细的解题思路分析，包括：

### 1. 🎯 核心算法识别
- 这道题考察什么算法/数据结构？
- 为什么选择这个算法？

### 2. 💡 解题思路（分步说明）
- 第一步做什么？
- 第二步做什么？
- ...（逐步说明完整思路）

### 3. ⚠️ 关键注意点
- 有哪些边界情况需要处理？
- 容易出错的地方是什么？

### 4. ⏱️ 复杂度分析
- 时间复杂度是多少？为什么？
- 空间复杂度是多少？

### 5. 💻 关键代码片段（伪代码或关键逻辑）
```
// 只给出核心逻辑的伪代码，不要给完整可运行的代码
```

**重要约束**：
- ❌ 不要推荐其他题目
- ❌ 不要输出Python工具调用代码
- ❌ 不要给出完整的AC代码
- ✅ 专注于分析当前这道题
- ✅ 用清晰的Markdown格式输出
- ✅ 引导用户思考而非直接给答案
"""
        # 注入 RAG 上下文
        if rag_context:
            problem_context = f"[知识库参考资料]:\n{rag_context}\n[参考资料结束]\n\n{problem_context}"
        
        # 使用agent生成解题指导
        t_llm = time.time()
        response = self.agent.run(problem_context)
        llm_time = round(time.time() - t_llm, 2)
        parts = []
        if rag_timing.get("_elapsed"):
            parts.append(f"RAG检索: {rag_timing['_elapsed']}s")
        parts.append(f"题目分析生成: {llm_time}s")
        response += f"\n\n---\n> ⏱ {' | '.join(parts)}"
        return response
    
    def search_memory(self, query: str, top_k: int = 3) -> str:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回的记忆数量
            
        Returns:
            相关记忆的文本描述
        """
        if not self.has_memory or not self.memory_manager:
            return ""
            
        try:
            results = self.memory_manager.search(query, top_k=top_k)
            if results:
                return format_search_results(results)
        except Exception as e:
            print(f"搜索记忆失败: {e}")
        return ""
    
    def save_to_memory(self, user_message: str, response: str):
        """
        保存对话到记忆
        
        Args:
            user_message: 用户消息
            response: Agent 响应
        """
        if not self.has_memory or not self.memory_manager:
            return
            
        try:
            # 保存用户消息
            self.memory_manager.add(f"用户: {user_message}", importance=0.7)
            # 保存 Agent 响应（简短版本）
            short_response = response[:200] + "..." if len(response) > 200 else response
            self.memory_manager.add(f"助手: {short_response}", importance=0.6)
        except Exception as e:
            print(f"保存记忆失败: {e}")
    
    def get_memory_summary(self) -> str:
        """
        获取记忆摘要
        
        Returns:
            记忆摘要文本
        """
        if not self.has_memory or not self.memory_manager:
            return "记忆功能未启用"
            
        try:
            return self.memory_manager.get_summary()
        except Exception as e:
            print(f"获取记忆摘要失败: {e}")
            return "暂无记忆摘要"
    
    def clear_memory(self) -> bool:
        """
        清空记忆
        
        Returns:
            是否成功
        """
        if not self.has_memory or not self.memory_manager:
            return False
        
        try:
            return self.memory_manager.clear()
        except Exception as e:
            print(f"清空记忆失败: {e}")
            return False
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除指定的记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否成功
        """
        if not self.has_memory or not self.memory_manager:
            return False
        
        try:
            return self.memory_manager.delete(memory_id)
        except Exception as e:
            print(f"删除记忆失败: {e}")
            return False
