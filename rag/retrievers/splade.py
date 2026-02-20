"""
SPLADE Learned Sparse Retriever
使用预训练 SPLADE 模型将文档和查询转为稀疏向量，通过点积计算相似度进行检索。
模型：naver/splade-cocondenser-ensembledistil
"""
import os
import json
import logging
from typing import List, Dict, Optional
from pathlib import Path

import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

from rag.models import KnowledgeChunk, RetrievedChunk

logger = logging.getLogger(__name__)

# 默认模型
DEFAULT_SPLADE_MODEL = "naver/splade-cocondenser-ensembledistil"

# 如果 HF_HOME 未设，默认指向项目所在盘符避免 C 盘空间不足
if not os.environ.get("HF_HOME"):
    _drive = os.path.splitdrive(os.path.abspath(__file__))[0]  # e.g. "F:"
    os.environ["HF_HOME"] = os.path.join(_drive + os.sep, "hf_cache")

# 索引持久化目录（与 BM25 共用 rag_data/）
SPLADE_INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rag_data")
SPLADE_INDEX_FILE = "splade_index.json"
SPLADE_CHUNKS_FILE = "splade_chunks.json"


class SpladeRetriever:
    """
    SPLADE Learned Sparse Retriever

    通过 SPLADE 模型将文本转为词汇表维度上的稀疏权重向量，
    利用稀疏向量点积进行高效检索。
    """

    def __init__(self, index_path: Optional[str] = None, model_name: str = DEFAULT_SPLADE_MODEL):
        """
        初始化 SPLADE 检索器。

        Args:
            index_path: 预构建索引文件所在目录，为 None 时使用默认路径
            model_name: HuggingFace 模型名称
        """
        self.index_dir = index_path or SPLADE_INDEX_DIR
        self.model_name = model_name

        # 模型和分词器（延迟加载）
        self._tokenizer = None
        self._model = None
        self._device = None

        # 索引数据
        self.sparse_index: Dict[str, Dict[str, float]] = {}  # chunk_id -> {token_id: weight}
        self.chunks: List[KnowledgeChunk] = []
        self.chunk_id_to_idx: Dict[str, int] = {}
        self._inverted_index: Dict[str, Dict[str, float]] = {}  # token_id -> {chunk_id: weight}

        # 尝试从磁盘加载已有索引
        self._try_load_index()

    def _ensure_model(self):
        """确保模型已加载（延迟加载以避免未使用时占用显存）"""
        if self._model is not None:
            return

        logger.info(f"加载 SPLADE 模型: {self.model_name}")
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self._model = AutoModelForMaskedLM.from_pretrained(
            self.model_name, use_safetensors=True
        ).to(self._device)
        self._model.eval()
        logger.info(f"SPLADE 模型加载完成 (device={self._device})")

    def _encode_sparse(self, text: str) -> Dict[str, float]:
        """
        将文本编码为 SPLADE 稀疏向量。

        SPLADE 输出每个词汇 token 的重要性权重（经过 log(1+ReLU) 变换），
        只保留权重 > 0 的 token。

        Args:
            text: 输入文本

        Returns:
            稀疏向量 {token_id_str: weight}
        """
        self._ensure_model()

        tokens = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(self._device)

        with torch.no_grad():
            output = self._model(**tokens)

        # SPLADE 聚合：对序列维度取 max，再做 log(1 + ReLU(x))
        logits = output.logits  # (1, seq_len, vocab_size)
        # 使用 attention_mask 遮蔽 padding token
        attention_mask = tokens["attention_mask"].unsqueeze(-1)  # (1, seq_len, 1)
        logits = logits * attention_mask

        sparse_vec = torch.max(
            torch.log1p(torch.relu(logits)),
            dim=1
        ).values.squeeze(0)  # (vocab_size,)

        # 提取非零项
        non_zero = sparse_vec.nonzero(as_tuple=True)[0]
        sparse_dict = {}
        for idx in non_zero:
            token_id = str(idx.item())
            weight = sparse_vec[idx].item()
            if weight > 0:
                sparse_dict[token_id] = round(weight, 6)

        return sparse_dict

    def build_index(self, chunks: List[KnowledgeChunk], batch_size: int = 16):
        """
        构建 SPLADE 稀疏索引。

        将所有 chunk 转为稀疏向量并保存为本地索引文件。

        Args:
            chunks: KnowledgeChunk 列表
            batch_size: 批量编码大小（控制显存）
        """
        self._ensure_model()

        print(f"🔄 构建 SPLADE 索引（{len(chunks)} 个 chunk）...")
        self.chunks = chunks
        self.sparse_index = {}
        self.chunk_id_to_idx = {}

        for i, chunk in enumerate(chunks):
            self.chunk_id_to_idx[chunk.chunk_id] = i
            sparse_vec = self._encode_sparse(chunk.content)
            self.sparse_index[chunk.chunk_id] = sparse_vec

            if (i + 1) % 50 == 0 or (i + 1) == len(chunks):
                print(f"   已编码: {i + 1}/{len(chunks)}")

        print(f"✅ SPLADE 索引构建完成")

        # 构建倒排索引
        self._build_inverted_index()

        # 持久化
        self._save_index()

    def _build_inverted_index(self):
        """从 sparse_index 构建倒排索引，用于加速检索"""
        inv: Dict[str, Dict[str, float]] = {}
        for chunk_id, token_weights in self.sparse_index.items():
            for token_id, weight in token_weights.items():
                if token_id not in inv:
                    inv[token_id] = {}
                inv[token_id][chunk_id] = weight
        self._inverted_index = inv

    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievedChunk]:
        """
        使用 SPLADE 进行 learned sparse 检索。

        将 query 转为稀疏向量，与索引中每个 chunk 的稀疏向量
        计算点积（重叠 token 权重乘积之和），返回 top_k。

        Args:
            query: 用户查询
            top_k: 返回前 k 个结果

        Returns:
            RetrievedChunk 列表
        """
        if not self.sparse_index:
            logger.warning("SPLADE 索引未初始化")
            return []

        query_sparse = self._encode_sparse(query)

        # 使用倒排索引加速点积计算（只访问 query token 命中的文档）
        score_map: Dict[str, float] = {}
        if self._inverted_index:
            for token_id, q_weight in query_sparse.items():
                posting = self._inverted_index.get(token_id)
                if posting:
                    for chunk_id, d_weight in posting.items():
                        score_map[chunk_id] = score_map.get(chunk_id, 0.0) + q_weight * d_weight
        else:
            # 回退到原始遍历方式
            for chunk_id, doc_sparse in self.sparse_index.items():
                score = self._dot_product(query_sparse, doc_sparse)
                if score > 0:
                    score_map[chunk_id] = score

        # 排序取 top_k
        sorted_scores = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:top_k]

        retrieved = []
        for chunk_id, score in sorted_scores:
            idx = self.chunk_id_to_idx.get(chunk_id)
            if idx is not None and idx < len(self.chunks):
                retrieved.append(RetrievedChunk(
                    chunk=self.chunks[idx],
                    retriever_type="splade",
                    score=score,
                ))

        return retrieved

    @staticmethod
    def _dot_product(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        """
        计算两个稀疏向量的点积。

        score = sum(a_i * b_i) for overlapping tokens
        """
        # 以较小的向量为主循环
        if len(vec_a) > len(vec_b):
            vec_a, vec_b = vec_b, vec_a

        score = 0.0
        for token_id, weight_a in vec_a.items():
            weight_b = vec_b.get(token_id, 0.0)
            score += weight_a * weight_b
        return score

    def _save_index(self):
        """持久化 SPLADE 索引和 chunk 数据到磁盘"""
        os.makedirs(self.index_dir, exist_ok=True)

        # 保存稀疏索引
        index_path = os.path.join(self.index_dir, SPLADE_INDEX_FILE)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(self.sparse_index, f, ensure_ascii=False)
        logger.info(f"SPLADE 索引已保存到 {index_path}")

        # 保存 chunk 元数据
        chunks_path = os.path.join(self.index_dir, SPLADE_CHUNKS_FILE)
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
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"SPLADE chunk 数据已保存到 {chunks_path}")

    def _try_load_index(self):
        """从磁盘加载已有的 SPLADE 索引"""
        index_path = os.path.join(self.index_dir, SPLADE_INDEX_FILE)
        chunks_path = os.path.join(self.index_dir, SPLADE_CHUNKS_FILE)

        if not os.path.exists(index_path) or not os.path.exists(chunks_path):
            logger.info("未找到 SPLADE 索引文件，等待构建")
            return

        try:
            # 加载稀疏索引
            with open(index_path, "r", encoding="utf-8") as f:
                self.sparse_index = json.load(f)

            # 加载 chunk 数据
            with open(chunks_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.chunks = []
            self.chunk_id_to_idx = {}
            for i, item in enumerate(data):
                chunk = KnowledgeChunk(
                    chunk_id=item["chunk_id"],
                    content=item["content"],
                    source=item["source"],
                    chapter=item.get("chapter", ""),
                    section=item.get("section", ""),
                    keywords=item.get("keywords", []),
                )
                self.chunks.append(chunk)
                self.chunk_id_to_idx[chunk.chunk_id] = i

            print(f"✅ 从磁盘加载 SPLADE 索引（{len(self.chunks)} 个 chunk，{len(self.sparse_index)} 条稀疏向量）")
            # 构建倒排索引加速检索
            self._build_inverted_index()
        except Exception as e:
            logger.error(f"加载 SPLADE 索引失败: {e}")
            self.sparse_index = {}
            self.chunks = []
            self.chunk_id_to_idx = {}
