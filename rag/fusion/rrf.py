"""
Reciprocal Rank Fusion (RRF) 模块
将多路检索器的结果通过 RRF 公式融合排序

公式：RRF_score(d) = Σ 1 / (k + rank_i(d))
其中 k 为常数（默认 60），rank_i(d) 为文档 d 在第 i 个检索器中的排名（从 1 开始）
"""
import logging
from typing import List, Dict

from rag.models import RetrievedChunk

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    results_list: List[List[RetrievedChunk]],
    k: int = 60,
    top_k: int = 15,
    debug: bool = False,
) -> List[RetrievedChunk]:
    """
    对多个检索器的结果进行 RRF 融合排序。

    Args:
        results_list: 多个检索器的结果列表，每个元素是一个
                      RetrievedChunk 的有序列表（按分数降序）
        k: RRF 常数，默认 60（控制长尾文档的权重衰减速率）
        top_k: 融合后返回的文档数量
        debug: 是否打印调试信息

    Returns:
        融合后按 RRF 分数降序排列的 RetrievedChunk 列表
    """
    # chunk_id → { rrf_score, chunk, retriever_types[] }
    fusion_map: Dict[str, dict] = {}

    for retriever_idx, results in enumerate(results_list):
        retriever_name = _get_retriever_name(results)

        if debug:
            logger.info(f"[RRF] 检索器 #{retriever_idx} ({retriever_name}) 返回 {len(results)} 个结果")
            for i, rc in enumerate(results[:3]):
                logger.info(f"  Top-{i+1}: {rc.chunk.chunk_id} | score={rc.score:.4f} | {rc.chunk.section}")

        for rank, rc in enumerate(results, start=1):
            cid = rc.chunk.chunk_id
            rrf_score = 1.0 / (k + rank)

            if cid not in fusion_map:
                fusion_map[cid] = {
                    "rrf_score": 0.0,
                    "chunk": rc.chunk,
                    "retriever_types": [],
                }

            fusion_map[cid]["rrf_score"] += rrf_score
            if retriever_name not in fusion_map[cid]["retriever_types"]:
                fusion_map[cid]["retriever_types"].append(retriever_name)

    # 按 RRF 分数降序排序
    sorted_items = sorted(fusion_map.values(), key=lambda x: x["rrf_score"], reverse=True)

    # 构造返回结果
    fused_results: List[RetrievedChunk] = []
    for item in sorted_items[:top_k]:
        retriever_type_str = "+".join(item["retriever_types"])
        fused_results.append(RetrievedChunk(
            chunk=item["chunk"],
            retriever_type=retriever_type_str,
            score=item["rrf_score"],
        ))

    if debug:
        logger.info(f"[RRF] 融合后共 {len(fusion_map)} 个文档，返回 Top-{top_k}")
        for i, rc in enumerate(fused_results[:5]):
            logger.info(
                f"  Fused Top-{i+1}: {rc.chunk.chunk_id} | "
                f"rrf_score={rc.score:.6f} | "
                f"retrievers={rc.retriever_type} | "
                f"{rc.chunk.section}"
            )

    return fused_results


def _get_retriever_name(results: List[RetrievedChunk]) -> str:
    """从结果列表中推断检索器名称"""
    if not results:
        return "unknown"
    return results[0].retriever_type
