"""
简化的记忆管理器 - 只使用 Qdrant 向量数据库，不依赖 Neo4j
"""
import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid
from datetime import datetime
import http.client as http_client

# 禁用 HTTP 调试日志
http_client.HTTPConnection.debuglevel = 0


class SimpleMemoryManager:
    """简化的记忆管理器，只使用 Qdrant 向量搜索"""
    
    def __init__(self, user_id: str = "default_user"):
        """
        初始化记忆管理器
        
        Args:
            user_id: 用户唯一标识
        """
        self.user_id = user_id
        self.collection_name = os.getenv("QDRANT_COLLECTION", "hello_agents_vectors_1024")
        
        # 连接到 Qdrant
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        
        if not qdrant_url or not qdrant_api_key:
            raise ValueError("需要配置 QDRANT_URL 和 QDRANT_API_KEY")
        
        self.client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30
        )
        
        # 初始化 embedding 模型
        self._init_embedder()
        
        # 存储本地记忆（用于摘要）
        self.memories = []
        
        # 从Qdrant加载已有记忆到本地列表
        self._load_existing_memories()
        
        print(f"✅ 简化记忆管理器初始化成功（用户: {user_id}，已加载 {len(self.memories)} 条记忆）")
    
    def _init_embedder(self):
        """初始化 embedding 模型"""
        try:
            from dashscope import TextEmbedding
            self.embed_model_name = os.getenv("EMBED_MODEL_NAME", "text-embedding-v3")
            self.embed_api_key = os.getenv("EMBED_API_KEY")
            
            if not self.embed_api_key:
                raise ValueError("需要配置 EMBED_API_KEY")
            
            print(f"✅ 使用 DashScope Embedding: {self.embed_model_name}")
        except ImportError:
            raise ValueError("需要安装 dashscope: pip install dashscope")
    
    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的向量表示"""
        from dashscope import TextEmbedding
        
        try:
            response = TextEmbedding.call(
                model=self.embed_model_name,
                input=text,
                api_key=self.embed_api_key
            )
            
            if response.status_code == 200:
                return response.output['embeddings'][0]['embedding']
            else:
                raise ValueError(f"Embedding 失败: {response.message}")
        except Exception as e:
            print(f"❌ 获取 embedding 失败: {e}")
            raise
    
    def add(self, content: str, importance: float = 0.5) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            importance: 重要性 (0-1)
            
        Returns:
            记忆 ID
        """
        try:
            # 生成 UUID 作为记忆 ID
            memory_id = str(uuid.uuid4())
            
            # 获取向量
            vector = self._get_embedding(content)
            
            # 存储到 Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=memory_id,
                        vector=vector,
                        payload={
                            "user_id": self.user_id,
                            "content": content,
                            "importance": importance,
                            "timestamp": datetime.now().isoformat(),
                            "type": "memory"
                        }
                    )
                ]
            )
            
            # 添加到本地记忆列表（避免重复）
            memory_dict = {
                "id": memory_id,
                "content": content,
                "importance": importance,
                "timestamp": datetime.now().isoformat()
            }
            # 检查是否已存在
            if not any(m['id'] == memory_id for m in self.memories):
                self.memories.append(memory_dict)
            
            return memory_id
        except Exception as e:
            print(f"❌ 添加记忆失败: {e}")
            return None
    
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            query: 查询文本
            top_k: 返回的记忆数量
            
        Returns:
            相关记忆列表
        """
        try:
            # 获取查询向量
            query_vector = self._get_embedding(query)
            
            # 在 Qdrant 中搜索
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=self.user_id)
                        )
                    ]
                ),
                limit=top_k
            )
            
            memories = []
            for result in results:
                memories.append({
                    "id": result.id,
                    "content": result.payload.get("content", ""),
                    "importance": result.payload.get("importance", 0.5),
                    "score": result.score,
                    "timestamp": result.payload.get("timestamp", "")
                })
            
            return memories
        except Exception as e:
            print(f"❌ 搜索记忆失败: {e}")
            return []

    def get_recent_memories(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的记忆列表
        
        Args:
            limit: 返回数量
            
        Returns:
            记忆列表
        """
        try:
            # 使用 scroll 获取最近的记录
            records, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=self.user_id)
                        )
                    ]
                ),
                limit=limit,
                with_payload=True,
                with_vectors=False
            )
            
            memories = []
            for record in records:
                memories.append({
                    "id": record.id,
                    "content": record.payload.get("content", ""),
                    "importance": record.payload.get("importance", 0.5),
                    "timestamp": record.payload.get("timestamp", ""),
                    "type": record.payload.get("type", "memory")
                })
            
            # 按 timestamp 倒序排序
            memories.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return memories
        except Exception as e:
            print(f"❌ 获取记忆列表失败: {e}")
            return []
    
    def get_summary(self) -> str:
        """获取记忆摘要"""
        if not self.memories:
            return "暂无记忆"
        
        summary = f"📊 记忆摘要\n"
        summary += f"总记忆数: {len(self.memories)}\n"
        
        # 按重要性排序
        sorted_memories = sorted(
            self.memories,
            key=lambda x: x.get("importance", 0),
            reverse=True
        )
        
        # 显示最重要的 5 条
        summary += "\n最重要的记忆:\n"
        for i, mem in enumerate(sorted_memories[:5], 1):
            content = mem["content"][:50] + "..." if len(mem["content"]) > 50 else mem["content"]
            summary += f"{i}. {content} (重要性: {mem['importance']:.2f})\n"
        
        return summary
    
    def delete(self, memory_id: str) -> bool:
        """
        删除指定的记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否成功
        """
        try:
            # 1. 从Qdrant中删除
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    points=[memory_id]
                )
            )
            
            # 2. 从本地列表中删除
            self.memories = [m for m in self.memories if m['id'] != memory_id]
            
            print(f"✅ 已删除记忆: {memory_id}")
            return True
        except Exception as e:
            print(f"❌ 删除记忆失败: {e}")
            return False
    
    def _load_existing_memories(self):
        """从Qdrant加载已有记忆到本地列表"""
        try:
            recent_memories = self.get_recent_memories(limit=100)  # 加载最近100条
            for mem in recent_memories:
                # 转换为本地列表格式
                self.memories.append({
                    "id": mem["id"],
                    "content": mem["content"],
                    "importance": mem["importance"],
                    "timestamp": mem["timestamp"]
                })
            print(f"✅ 已从Qdrant加载 {len(self.memories)} 条记忆")
        except Exception as e:
            print(f"⚠️ 加载已有记忆失败: {e}")
            # 失败时保持空列表，不影响后续使用
    
    def clear(self) -> bool:
        """清空记忆（包括Qdrant和本地列表）"""
        try:
            # 1. 清空Qdrant中的用户记忆
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="user_id",
                                match=models.MatchValue(value=self.user_id)
                            )
                        ]
                    )
                )
            )
            
            # 2. 清空本地列表
            self.memories = []
            
            print(f"✅ 已清空用户 {self.user_id} 的所有记忆（Qdrant + 本地）")
            return True
        except Exception as e:
            print(f"❌ 清空记忆失败: {e}")
            return False


def format_search_results(memories: List[Dict[str, Any]]) -> str:
    """格式化搜索结果"""
    if not memories:
        return "未找到相关记忆"
    
    result = f"🔍 找到 {len(memories)} 条相关记忆:\n\n"
    for i, mem in enumerate(memories, 1):
        result += f"{i}. {mem['content']}\n"
        result += f"   相关度: {mem['score']:.3f} | 重要性: {mem['importance']:.2f}\n\n"
    
    return result
