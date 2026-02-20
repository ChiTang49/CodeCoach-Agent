"""
RAG 文档预处理脚本
用于将 PDF 文件解析、切分并索引到向量数据库
只需运行一次，后续启动无需重复执行

用法：
    conda activate agent
    python rag_ingest.py
"""
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from rag.ingestion import parse_pdf
from rag.embedding import EmbeddingClient
from rag.retrievers.dense import DenseRetriever, RAG_COLLECTION
from rag.retrievers.sparse import SparseRetriever
from rag.retrievers.splade import SpladeRetriever
from qdrant_client import QdrantClient


def main():
    # PDF 文件路径
    pdf_path = os.path.join(os.path.dirname(__file__), "files", "OI-wiki_v20260215_1116.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"❌ PDF 文件不存在: {pdf_path}")
        print("   请确保文件已放在 files/ 目录下")
        sys.exit(1)
    
    print("=" * 60)
    print("📚 RAG 文档预处理工具")
    print("=" * 60)
    print(f"文件: {pdf_path}")
    print(f"文件大小: {os.path.getsize(pdf_path) / 1024 / 1024:.1f} MB")
    print()
    
    # Step 1: 解析 PDF
    print("📄 [Step 1/4] 解析 PDF 文档...")
    start = time.time()
    chunks = parse_pdf(pdf_path)
    print(f"   耗时: {time.time() - start:.1f}s")
    print(f"   生成 {len(chunks)} 个 chunk")
    print()
    
    # 打印一些统计信息
    chapters = set(c.chapter for c in chunks)
    print(f"   识别到 {len(chapters)} 个章节:")
    for ch in sorted(chapters)[:20]:
        ch_count = sum(1 for c in chunks if c.chapter == ch)
        print(f"     - {ch} ({ch_count} chunks)")
    if len(chapters) > 20:
        print(f"     ... 还有 {len(chapters) - 20} 个章节")
    print()
    
    # Step 2: 构建 BM25 索引
    print("🔍 [Step 2/5] 构建 BM25 索引...")
    start = time.time()
    sparse_retriever = SparseRetriever(chunks=chunks)
    print(f"   耗时: {time.time() - start:.1f}s")
    print()

    # Step 2.5: 构建 SPLADE 索引
    print("🧪 [Step 3/5] 构建 SPLADE 索引...")
    print("   首次运行需要下载 SPLADE 模型（~500MB），请耐心等待...")
    start = time.time()
    splade_retriever = SpladeRetriever()
    splade_retriever.build_index(chunks)
    print(f"   耗时: {time.time() - start:.1f}s")
    print()

    # Step 3: 构建向量索引
    print("🧠 [Step 4/5] 构建向量索引（Qdrant + DashScope Embedding）...")
    print("   这可能需要几分钟，取决于 chunk 数量...")
    start = time.time()
    
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=60)
    embedding_client = EmbeddingClient()
    
    dense_retriever = DenseRetriever(
        qdrant_client=qdrant_client,
        embedding_client=embedding_client
    )
    
    # 确保集合存在（先删除旧的重建）
    try:
        collections = [c.name for c in qdrant_client.get_collections().collections]
        if RAG_COLLECTION in collections:
            print(f"   删除已有集合 {RAG_COLLECTION}...")
            qdrant_client.delete_collection(RAG_COLLECTION)
    except Exception as e:
        print(f"   检查集合时出错: {e}")
    
    # 获取一个样本 embedding 来确定维度
    sample_emb = embedding_client.embed("测试")
    vector_size = len(sample_emb)
    print(f"   Embedding 维度: {vector_size}")
    
    dense_retriever.ensure_collection(vector_size=vector_size)
    
    # 索引所有 chunks
    dense_retriever.index_chunks(chunks, batch_size=6)
    
    print(f"   耗时: {time.time() - start:.1f}s")
    print()
    
    # Step 5: 验证
    print("✅ [Step 5/5] 验证索引...")
    
    # 验证 Qdrant
    collection_info = qdrant_client.get_collection(RAG_COLLECTION)
    print(f"   Qdrant 集合 '{RAG_COLLECTION}': {collection_info.points_count} 个点")
    
    # 验证 BM25
    test_results = sparse_retriever.retrieve("动态规划", top_k=3)
    print(f"   BM25 测试检索 '动态规划': 找到 {len(test_results)} 个结果")
    
    # 验证 Dense
    test_results = dense_retriever.retrieve("什么是贪心算法", top_k=3)
    print(f"   向量检索测试 '什么是贪心算法': 找到 {len(test_results)} 个结果")
    
    # 验证 SPLADE
    test_results = splade_retriever.retrieve("动态规划状态转移", top_k=3)
    print(f"   SPLADE 检索测试 '动态规划状态转移': 找到 {len(test_results)} 个结果")
    
    print()
    print("=" * 60)
    print("🎉 预处理完成！RAG 模块已就绪。")
    print("   现在可以启动应用使用 RAG 知识问答功能。")
    print("=" * 60)


if __name__ == "__main__":
    main()
