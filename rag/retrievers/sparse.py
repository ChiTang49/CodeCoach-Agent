"""
Sparse Retriever - 基于 BM25 的关键词检索器
适合精确术语匹配和英文缩写检索
"""
import json
import os
import logging
from typing import List, Optional
from pathlib import Path

import jieba
from rank_bm25 import BM25Okapi

from rag.models import KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)

# BM25 索引持久化路径
BM25_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_data")


class SparseRetriever:
    """BM25 关键词检索器"""
    
    def __init__(self, chunks: Optional[List[KnowledgeChunk]] = None):
        """
        Args:
            chunks: 已解析的 chunk 列表（用于构建索引）；
                    如果为 None，则尝试从磁盘加载索引
        """
        self.chunks: List[KnowledgeChunk] = []
        self.bm25: Optional[BM25Okapi] = None
        self.tokenized_corpus: List[List[str]] = []
        
        if chunks:
            self.build_index(chunks)
        else:
            self._try_load_index()
    
    def build_index(self, chunks: List[KnowledgeChunk]):
        """
        构建 BM25 索引
        """
        print(f"🔄 构建 BM25 索引（{len(chunks)} 个 chunk）...")
        self.chunks = chunks
        
        # jieba 分词
        self.tokenized_corpus = []
        for chunk in chunks:
            tokens = list(jieba.cut(chunk.content))
            # 同时加入 keywords 提升术语权重
            tokens.extend(chunk.keywords)
            self.tokenized_corpus.append(tokens)
        
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        print(f"✅ BM25 索引构建完成")
        
        # 持久化
        self._save_index()
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedChunk]:
        """
        使用 BM25 进行关键词检索
        
        Args:
            query: 用户查询
            top_k: 返回前 k 个结果
            
        Returns:
            RetrievedChunk 列表
        """
        if self.bm25 is None:
            logger.warning("BM25 索引未初始化")
            return []
        
        query_tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(query_tokens)
        
        # 获取 top_k 索引
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        
        retrieved = []
        for idx in top_indices:
            if scores[idx] > 0:
                retrieved.append(RetrievedChunk(
                    chunk=self.chunks[idx],
                    retriever_type="bm25",
                    score=float(scores[idx])
                ))
        
        return retrieved
    
    def _save_index(self):
        """持久化 chunk 数据到磁盘（BM25 索引每次从 chunk 重建）"""
        os.makedirs(BM25_INDEX_DIR, exist_ok=True)
        index_path = os.path.join(BM25_INDEX_DIR, "bm25_chunks.json")
        
        data = []
        for chunk in self.chunks:
            data.append({
                "chunk_id": chunk.chunk_id,
                "content": chunk.content,
                "source": chunk.source,
                "chapter": chunk.chapter,
                "section": chunk.section,
                "keywords": chunk.keywords,
            })
        
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"BM25 chunk 数据已保存到 {index_path}")
    
    def _try_load_index(self):
        """从磁盘加载 chunk 数据并重建 BM25 索引"""
        index_path = os.path.join(BM25_INDEX_DIR, "bm25_chunks.json")
        if not os.path.exists(index_path):
            logger.info("未找到 BM25 索引文件，等待构建")
            return
        
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            chunks = []
            for item in data:
                chunks.append(KnowledgeChunk(
                    chunk_id=item["chunk_id"],
                    content=item["content"],
                    source=item["source"],
                    chapter=item.get("chapter", ""),
                    section=item.get("section", ""),
                    keywords=item.get("keywords", []),
                ))
            
            if chunks:
                self.build_index(chunks)
                print(f"✅ 从磁盘加载 BM25 索引（{len(chunks)} 个 chunk）")
        except Exception as e:
            logger.error(f"加载 BM25 索引失败: {e}")
