"""
Query Rewrite 模块
对用户 Query 进行术语扩展、同义表达增强和问题标准化
输出增强后的 query，用于提升检索效果
"""
import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

REWRITE_PROMPT = """你是一个算法竞赛知识查询改写助手。

请对用户问题进行：
1. 专业术语补全
2. 同义表达扩展
3. 标准化表达

要求：
- 保持原问题语义不变
- 只输出改写后的单条 query
- 不输出解释

用户问题：
{query}"""


def _get_llm_client():
    """获取 LLM 客户端（与系统其他模块一致）"""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model_id = os.getenv("LLM_MODEL_ID", "deepseek-chat")

    if not api_key:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        base_url = os.getenv("DASHSCOPE_BASE_URL")
        model_id = "qwen-plus"

    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model_id


def rewrite_query(query: str) -> str:
    """
    对用户 query 进行改写增强。

    功能：
    - 术语扩展（如 DP → 动态规划，BFS → 广度优先搜索）
    - 同义表达增强
    - 问题标准化

    Args:
        query: 原始用户 query

    Returns:
        改写增强后的 query；若改写失败则返回原 query
    """
    query = query.strip()
    if not query:
        return query

    try:
        client, model_id = _get_llm_client()

        prompt = REWRITE_PROMPT.format(query=query)

        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )

        rewritten = response.choices[0].message.content.strip()

        # 基本校验：改写结果不能为空，也不能太长（超过原文 5 倍）
        if not rewritten or len(rewritten) > len(query) * 5:
            logger.warning(f"Query Rewrite 结果异常，回退原 query: {rewritten}")
            return query

        logger.info(f"Query Rewrite: '{query}' → '{rewritten}'")
        return rewritten

    except Exception as e:
        logger.error(f"Query Rewrite 失败，回退原 query: {e}")
        return query
