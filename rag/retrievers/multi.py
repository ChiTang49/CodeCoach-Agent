"""
Multi-Retriever 管理器
并行调用多个 Retriever，合并去重结果
"""
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from rag.models import RetrievedChunk

logger = logging.getLogger(__name__)


class MultiRetriever:
    """多检索器管理器：并行召回 + 融合去重"""
    
    def __init__(self, retrievers: List):
        """
        Args:
            retrievers: Retriever 实例列表，每个必须实现 retrieve(query, top_k) 方法
        """
        self.retrievers = retrievers
    
    def retrieve(self, query: str, top_k: int = 15) -> List[RetrievedChunk]:
        """
        并行调用所有 retriever，合并去重，返回候选集合
        
        Args:
            query: 用户查询
            top_k: 每个 retriever 取的数量
            
        Returns:
            合并去重后的 RetrievedChunk 列表
        """
        all_results: List[RetrievedChunk] = []
        
        # 并行召回
        with ThreadPoolExecutor(max_workers=len(self.retrievers)) as executor:
            futures = {}
            for retriever in self.retrievers:
                future = executor.submit(retriever.retrieve, query, top_k)
                futures[future] = retriever.__class__.__name__
            
            for future in as_completed(futures):
                retriever_name = futures[future]
                try:
                    results = future.result()
                    logger.info(f"{retriever_name} 返回 {len(results)} 个结果")
                    all_results.extend(results)
                except Exception as e:
                    logger.error(f"{retriever_name} 检索失败: {e}")
        
        # 去重融合
        merged = self._merge_and_dedup(all_results)
        
        logger.info(f"Multi-Retriever 合并后共 {len(merged)} 个候选")
        return merged
    
    def _merge_and_dedup(self, results: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        去重规则：
        - chunk_id 相同 → 只保留一个
        - score 取最大值
        - 同时记录来自哪些 retriever
        """
        chunk_map: Dict[str, RetrievedChunk] = {}
        
        for rc in results:
            cid = rc.chunk.chunk_id
            if cid in chunk_map:
                # 保留分数更高的
                if rc.score > chunk_map[cid].score:
                    # 用新的更高分数替换，但保留 retriever_type 合并信息
                    old_type = chunk_map[cid].retriever_type
                    new_type = rc.retriever_type
                    if new_type not in old_type:
                        merged_type = f"{old_type}+{new_type}"
                    else:
                        merged_type = old_type
                    chunk_map[cid] = RetrievedChunk(
                        chunk=rc.chunk,
                        retriever_type=merged_type,
                        score=rc.score
                    )
                else:
                    # 只更新 retriever_type
                    old = chunk_map[cid]
                    if rc.retriever_type not in old.retriever_type:
                        chunk_map[cid] = RetrievedChunk(
                            chunk=old.chunk,
                            retriever_type=f"{old.retriever_type}+{rc.retriever_type}",
                            score=old.score
                        )
            else:
                chunk_map[cid] = rc
        
        # 按分数降序排列
        merged = sorted(chunk_map.values(), key=lambda x: x.score, reverse=True)
        return merged
