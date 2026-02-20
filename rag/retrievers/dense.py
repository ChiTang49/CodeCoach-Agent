"""
Dense Retriever - 基于向量语义相似度的检索器
使用 Qdrant 向量数据库进行 ANN 检索
"""
import os
import logging
from typing import List

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from rag.models import KnowledgeChunk, RetrievedChunk
from rag.embedding import EmbeddingClient

logger = logging.getLogger(__name__)

# RAG 专用集合名
RAG_COLLECTION = "rag_knowledge_chunks"


class DenseRetriever:
    """语义向量检索器"""
    
    def __init__(self, qdrant_client: QdrantClient = None, embedding_client: EmbeddingClient = None):
        """
        Args:
            qdrant_client: 已初始化的 Qdrant 客户端（可复用）
            embedding_client: 已初始化的 Embedding 客户端（可复用）
        """
        if qdrant_client:
            self.client = qdrant_client
        else:
            qdrant_url = os.getenv("QDRANT_URL")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=30)
        
        self.embedding_client = embedding_client or EmbeddingClient()
        self.collection_name = RAG_COLLECTION
    
    def ensure_collection(self, vector_size: int = 1024):
        """确保 Qdrant 集合已创建"""
        collections = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in collections:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE
                )
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")
    
    def index_chunks(self, chunks: List[KnowledgeChunk], batch_size: int = 50):
        """
        将 chunks 索引到 Qdrant
        
        Args:
            chunks: KnowledgeChunk 列表
            batch_size: 每批上传数量
        """
        print(f"🔄 开始向量化并索引 {len(chunks)} 个 chunk ...")
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c.content for c in batch]
            
            # 批量生成 embedding
            embeddings = self.embedding_client.embed_batch(texts)
            
            # 构造 Qdrant points
            points = []
            for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
                point = qmodels.PointStruct(
                    id=abs(hash(chunk.chunk_id)) % (2**63),  # Qdrant 需要 int id
                    vector=emb,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "content": chunk.content,
                        "source": chunk.source,
                        "chapter": chunk.chapter,
                        "section": chunk.section,
                        "keywords": chunk.keywords,
                    }
                )
                points.append(point)
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            progress = min(i + batch_size, len(chunks))
            print(f"   已索引: {progress}/{len(chunks)}")
        
        print(f"✅ 向量索引完成")
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedChunk]:
        """
        使用向量语义相似度检索
        
        Args:
            query: 用户查询
            top_k: 返回前 k 个结果
            
        Returns:
            RetrievedChunk 列表
        """
        query_embedding = self.embedding_client.embed(query)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            with_payload=True
        )
        
        retrieved = []
        for r in results:
            payload = r.payload
            chunk = KnowledgeChunk(
                chunk_id=payload.get("chunk_id", ""),
                content=payload.get("content", ""),
                source=payload.get("source", ""),
                chapter=payload.get("chapter", ""),
                section=payload.get("section", ""),
                keywords=payload.get("keywords", []),
            )
            retrieved.append(RetrievedChunk(
                chunk=chunk,
                retriever_type="dense",
                score=r.score
            ))
        
        return retrieved
