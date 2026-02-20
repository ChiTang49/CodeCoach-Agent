"""
RAG 模块数据模型定义
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class KnowledgeChunk(BaseModel):
    """文档知识片段"""
    chunk_id: str                           # 唯一标识
    content: str                            # 片段文本内容
    source: str                             # 文档来源，如 "OI-wiki_v20260215_1116.pdf"
    chapter: str = ""                       # 章节标题，如 "动态规划"
    section: str = ""                       # 小节标题，如 "状态设计"
    keywords: List[str] = Field(default_factory=list)   # 术语列表
    embedding: Optional[List[float]] = None # 向量表示


class RetrievedChunk(BaseModel):
    """检索结果"""
    chunk: KnowledgeChunk
    retriever_type: str                     # "dense" | "bm25" | "section"
    score: float                            # 相关性分数


class RAGResult(BaseModel):
    """RAG 最终结果"""
    answer: str                             # LLM 最终回答
    evidence: List[RetrievedChunk] = Field(default_factory=list)  # 引用的证据
    query: str = ""                         # 原始查询
    timing: dict = Field(default_factory=dict)  # 各模块耗时（秒）
