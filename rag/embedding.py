"""
Embedding 工具模块
封装 DashScope embedding 调用，供各模块复用
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class EmbeddingClient:
    """DashScope Embedding 客户端"""
    
    def __init__(self):
        self.model_name = os.getenv("EMBED_MODEL_NAME", "text-embedding-v3")
        self.api_key = os.getenv("EMBED_API_KEY")
        if not self.api_key:
            raise ValueError("需要配置 EMBED_API_KEY 环境变量")
    
    def embed(self, text: str) -> List[float]:
        """获取单条文本的向量"""
        from dashscope import TextEmbedding
        
        response = TextEmbedding.call(
            model=self.model_name,
            input=text,
            api_key=self.api_key
        )
        if response.status_code == 200:
            return response.output['embeddings'][0]['embedding']
        else:
            raise ValueError(f"Embedding 失败: {response.message}")
    
    def embed_batch(self, texts: List[str], batch_size: int = 6) -> List[List[float]]:
        """
        批量获取向量（DashScope 单次最多支持 10 条，保守用 6）
        """
        from dashscope import TextEmbedding
        
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = TextEmbedding.call(
                model=self.model_name,
                input=batch,
                api_key=self.api_key
            )
            if response.status_code == 200:
                embeddings = [item['embedding'] for item in response.output['embeddings']]
                all_embeddings.extend(embeddings)
            else:
                raise ValueError(f"Batch Embedding 失败 (batch {i}): {response.message}")
        return all_embeddings
