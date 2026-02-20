"""
Section Retriever - 基于章节/小节标题的结构检索器
模拟"翻书"操作，通过标题匹配定位知识位置
"""
import logging
from typing import List, Optional

import jieba

from rag.models import KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)


class SectionRetriever:
    """章节标题结构检索器"""
    
    def __init__(self, chunks: Optional[List[KnowledgeChunk]] = None):
        """
        Args:
            chunks: 已解析的 chunk 列表
        """
        self.chunks: List[KnowledgeChunk] = chunks or []
    
    def set_chunks(self, chunks: List[KnowledgeChunk]):
        """设置/更新 chunk 列表"""
        self.chunks = chunks
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedChunk]:
        """
        基于章节/小节标题匹配检索
        
        匹配策略：
        1. 查询分词
        2. 对每个 chunk 的 chapter、section、keywords 进行匹配打分
        3. 按匹配分数排序
        
        Args:
            query: 用户查询
            top_k: 返回前 k 个结果
            
        Returns:
            RetrievedChunk 列表
        """
        if not self.chunks:
            logger.warning("Section Retriever 无 chunk 数据")
            return []
        
        query_tokens = set(jieba.cut(query))
        # 移除停用词
        stop_words = {'的', '了', '是', '在', '有', '和', '与', '或', '对', '中', '这', '那',
                       '什么', '怎么', '如何', '为什么', '请', '我', '你', '他', '她', '它',
                       '吗', '呢', '吧', '啊', '哈', '嗯', '好', '用', '个', '一', '不'}
        query_tokens = query_tokens - stop_words
        
        scored_chunks = []
        for chunk in self.chunks:
            score = 0.0
            
            # 章节标题匹配（高权重）
            chapter_tokens = set(jieba.cut(chunk.chapter))
            chapter_match = len(query_tokens & chapter_tokens)
            score += chapter_match * 3.0
            
            # 小节标题匹配（中权重）
            section_tokens = set(jieba.cut(chunk.section))
            section_match = len(query_tokens & section_tokens)
            score += section_match * 2.0
            
            # 关键词匹配（低权重）
            keyword_set = set(chunk.keywords)
            keyword_match = len(query_tokens & keyword_set)
            score += keyword_match * 1.5
            
            # 直接子串匹配加分（精确匹配奖励）
            for token in query_tokens:
                if len(token) >= 2:
                    if token in chunk.chapter:
                        score += 2.0
                    if token in chunk.section:
                        score += 1.5
            
            if score > 0:
                scored_chunks.append((chunk, score))
        
        # 排序取 top_k
        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        
        retrieved = []
        for chunk, score in scored_chunks[:top_k]:
            retrieved.append(RetrievedChunk(
                chunk=chunk,
                retriever_type="section",
                score=score
            ))
        
        return retrieved
