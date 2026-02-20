"""
SPLADE 索引单独构建脚本
复用已有的 BM25 chunk 数据（rag_data/bm25_chunks.json），
无需重新解析 PDF 或重建 Qdrant/BM25 索引。

用法：
    conda activate agent
    python build_splade_index.py
"""
import os
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()

from rag.models import KnowledgeChunk
from rag.retrievers.splade import SpladeRetriever


def main():
    chunks_path = os.path.join(os.path.dirname(__file__), "rag_data", "bm25_chunks.json")

    if not os.path.exists(chunks_path):
        print(f"❌ 未找到 chunk 数据: {chunks_path}")
        print("   请先运行 rag_ingest.py 完成 PDF 解析和基础索引构建")
        sys.exit(1)

    # 加载已有 chunk 数据
    print("📂 加载已有 chunk 数据...")
    with open(chunks_path, "r", encoding="utf-8") as f:
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

    print(f"   共 {len(chunks)} 个 chunk")
    print()

    # 构建 SPLADE 索引
    print("🧪 构建 SPLADE 索引...")
    print("   首次运行需要下载 SPLADE 模型（~500MB），请耐心等待...")
    start = time.time()

    splade = SpladeRetriever()
    splade.build_index(chunks)

    elapsed = time.time() - start
    print(f"   耗时: {elapsed:.1f}s")
    print()

    # 验证
    print("✅ 验证 SPLADE 检索...")
    test_results = splade.retrieve("动态规划状态转移", top_k=3)
    print(f"   测试检索 '动态规划状态转移': 找到 {len(test_results)} 个结果")
    for i, rc in enumerate(test_results):
        print(f"   {i+1}. [{rc.chunk.chapter}] {rc.chunk.section} (score={rc.score:.4f})")

    print()
    print("🎉 SPLADE 索引构建完成！")


if __name__ == "__main__":
    main()
