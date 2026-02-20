"""
LLM Re-Ranking 模块
使用 LLM 对候选 chunk 进行相关性重排序
"""
import os
import json
import logging
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

from rag.models import RetrievedChunk

load_dotenv()
logger = logging.getLogger(__name__)

RERANK_PROMPT_TEMPLATE = """你是一个算法知识助手，需要判断候选知识片段与用户问题的相关性。

用户问题：{query}

以下是候选知识片段（编号从 0 开始）：
{chunk_list}

请从中选出最有助于回答用户问题的 {top_k} 个片段，并按相关性从高到低排序。
只需返回一个 JSON 数组，包含选中片段的编号，例如：[2, 0, 5, 3]
不要输出任何其他内容，只输出 JSON 数组。"""


class LLMReranker:
    """使用 LLM 对候选 chunk 进行重排序"""
    
    def __init__(self):
        """初始化 LLM 客户端"""
        # 优先使用 DeepSeek（便宜快速），也可切换为 DashScope
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model_id = os.getenv("LLM_MODEL_ID", "deepseek-chat")
        
        if not api_key:
            # fallback 到 DashScope
            api_key = os.getenv("DASHSCOPE_API_KEY")
            base_url = os.getenv("DASHSCOPE_BASE_URL")
            model_id = "qwen-plus"
        
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_id = model_id
    
    def rerank(
        self,
        query: str,
        candidates: List[RetrievedChunk],
        top_k: int = 5
    ) -> List[RetrievedChunk]:
        """
        使用 LLM 重排序候选 chunk
        
        Args:
            query: 用户查询
            candidates: Multi-Retriever 返回的候选列表
            top_k: 最终选取数量
            
        Returns:
            重排序后的 top_k RetrievedChunk 列表
        """
        if not candidates:
            return []
        
        if len(candidates) <= top_k:
            return candidates
        
        # 构造 chunk 列表描述
        chunk_descriptions = []
        for i, rc in enumerate(candidates):
            desc = (
                f"[{i}] 来源: {rc.chunk.source} | "
                f"章节: {rc.chunk.chapter} | "
                f"小节: {rc.chunk.section}\n"
                f"内容: {rc.chunk.content[:300]}..."
                if len(rc.chunk.content) > 300 else
                f"[{i}] 来源: {rc.chunk.source} | "
                f"章节: {rc.chunk.chapter} | "
                f"小节: {rc.chunk.section}\n"
                f"内容: {rc.chunk.content}"
            )
            chunk_descriptions.append(desc)
        
        chunk_list_str = "\n\n".join(chunk_descriptions)
        
        prompt = RERANK_PROMPT_TEMPLATE.format(
            query=query,
            chunk_list=chunk_list_str,
            top_k=top_k
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200
            )
            
            content = response.choices[0].message.content.strip()
            # 提取 JSON 数组
            # 尝试直接解析，或从文本中提取
            try:
                indices = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从文本中提取数组
                import re
                match = re.search(r'\[[\d\s,]+\]', content)
                if match:
                    indices = json.loads(match.group())
                else:
                    logger.warning(f"Re-Ranking LLM 返回格式异常: {content}")
                    return candidates[:top_k]
            
            # 验证并提取
            reranked = []
            seen = set()
            for idx in indices:
                if isinstance(idx, int) and 0 <= idx < len(candidates) and idx not in seen:
                    reranked.append(candidates[idx])
                    seen.add(idx)
                if len(reranked) >= top_k:
                    break
            
            # 如果 LLM 返回的结果不够，用原始排序补充
            if len(reranked) < top_k:
                for rc in candidates:
                    if rc.chunk.chunk_id not in {r.chunk.chunk_id for r in reranked}:
                        reranked.append(rc)
                    if len(reranked) >= top_k:
                        break
            
            logger.info(f"Re-Ranking 完成，选出 {len(reranked)} 个 chunk")
            return reranked
            
        except Exception as e:
            logger.error(f"Re-Ranking 失败: {e}，退回到原始排序")
            return candidates[:top_k]
