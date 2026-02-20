"""
RAGService - RAG 统一服务接口
# Agent 和 Frontend 只需调用 RAGService.answer() 即可完成完整 RAG 流程
"""
import os
import time
import logging
from typing import List, Optional
from dotenv import load_dotenv
from openai import OpenAI

from qdrant_client import QdrantClient

from rag.models import KnowledgeChunk, RetrievedChunk, RAGResult
from rag.embedding import EmbeddingClient
from rag.retrievers.dense import DenseRetriever
from rag.retrievers.sparse import SparseRetriever
from rag.retrievers.section import SectionRetriever
from rag.retrievers.multi import MultiRetriever
from rag.retrievers.splade import SpladeRetriever
from rag.reranker import LLMReranker
from rag.rewrite.query_rewrite import rewrite_query
from rag.fusion.rrf import reciprocal_rank_fusion

load_dotenv()
logger = logging.getLogger(__name__)

ANSWER_PROMPT_TEMPLATE = """你是一个专业的算法知识助手。请根据以下参考知识片段回答用户的问题。

要求：
1. 只根据提供的参考知识回答，不要编造信息
2. 如果参考知识不足以完整回答问题，请说明哪部分信息不足
3. 回答要清晰、有条理，使用 Markdown 格式
4. 如果涉及代码，请使用代码块
5. 在回答末尾标注参考来源（章节信息）

参考知识：
{evidence}

用户问题：{query}

请回答："""


class RAGService:
    """
    RAG 统一服务
    
    完整流程：
    User Query → Query Preprocess → Multi-Retriever 并行召回 
    → Candidate Merge & Dedup → LLM Re-Ranking → Top-K Evidence Selection 
    → LLM Answer Generation（Grounded）
    """
    
    def __init__(self):
        """初始化 RAG 服务的所有组件"""
        logger.info("🚀 初始化 RAG 服务...")
        
        # 共享的 Qdrant 客户端
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        
        if not qdrant_url or not qdrant_api_key:
            raise ValueError("需要配置 QDRANT_URL 和 QDRANT_API_KEY")
        
        self.qdrant_client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=30
        )
        
        # 共享的 Embedding 客户端
        self.embedding_client = EmbeddingClient()
        
        # 初始化检索器
        self.dense_retriever = DenseRetriever(
            qdrant_client=self.qdrant_client,
            embedding_client=self.embedding_client
        )
        self.sparse_retriever = SparseRetriever()  # 从磁盘加载索引
        self.section_retriever = SectionRetriever()
        self.splade_retriever = SpladeRetriever()   # SPLADE learned sparse retriever
        
        # 设置 section_retriever 的 chunks（复用 sparse 的）
        if self.sparse_retriever.chunks:
            self.section_retriever.set_chunks(self.sparse_retriever.chunks)
        
        # Multi-Retriever（四路检索）
        self.multi_retriever = MultiRetriever([
            self.dense_retriever,
            self.sparse_retriever,
            self.section_retriever,
            self.splade_retriever,
        ])
        
        # Re-Ranker
        self.reranker = LLMReranker()
        
        # 答案生成 LLM
        api_key = os.getenv("DEEPSEEK_API_KEY")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model_id = os.getenv("LLM_MODEL_ID", "deepseek-chat")
        
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY")
            base_url = os.getenv("DASHSCOPE_BASE_URL")
            model_id = "qwen-plus"
        
        self.llm_client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_id = model_id
        
        self._initialized = True
        logger.info("✅ RAG 服务初始化完成")
    
    def answer(
        self,
        query: str,
        top_k_retrieve: int = 15,
        top_k_rerank: int = 5,
        use_llm_rerank: bool = False,
        use_query_rewrite: bool = True,
        use_rrf: bool = True,
        debug: bool = False,
    ) -> str:
        """
        完整 RAG 流程，返回最终回答
        
        Args:
            query: 用户问题
            top_k_retrieve: 每个 retriever 召回数量
            top_k_rerank: re-ranking 后保留数量
            use_llm_rerank: 是否使用 LLM 进行重排序（耗时较长但更准确）
            use_query_rewrite: 是否启用 Query Rewrite
            use_rrf: 是否使用 RRF 融合排序
            debug: 是否启用调试日志
            
        Returns:
            LLM 生成的最终回答
        """
        result = self.answer_with_evidence(
            query, top_k_retrieve, top_k_rerank, use_llm_rerank,
            use_query_rewrite=use_query_rewrite, use_rrf=use_rrf, debug=debug
        )
        return result.answer
    
    def answer_with_evidence(
        self, 
        query: str, 
        top_k_retrieve: int = 15, 
        top_k_rerank: int = 5,
        use_llm_rerank: bool = False,
        use_query_rewrite: bool = True,
        use_rrf: bool = True,
        debug: bool = False,
    ) -> RAGResult:
        """
        完整 RAG 流程，返回回答和证据
        
        流程：
        1. Query Rewrite（可选）
        2. 四路并行检索（Dense + BM25 + Section + SPLADE）
        3. RRF 融合排序（可选，否则使用旧的合并去重）
        4. Re-Ranking（可选）
        5. LLM Answer Generation
        
        Args:
            query: 用户问题
            top_k_retrieve: 每个 retriever 召回数量
            top_k_rerank: re-ranking 后保留数量
            use_llm_rerank: 是否使用 LLM 进行重排序
            use_query_rewrite: 是否启用 Query Rewrite
            use_rrf: 是否使用 RRF 融合排序
            debug: 是否启用调试日志
            
        Returns:
            RAGResult（含 answer 和 evidence）
        """
        logger.info(f"📝 RAG 查询: {query}")
        timing = {}
        t_total_start = time.time()
        
        # Step 1: Query Rewrite
        t0 = time.time()
        if use_query_rewrite:
            processed_query = rewrite_query(query)
            logger.info(f"   Query Rewrite: '{query}' → '{processed_query}'")
        else:
            processed_query = query.strip()
        timing["query_rewrite"] = round(time.time() - t0, 2)
        
        # Step 2: 四路并行检索 + 融合
        t0 = time.time()
        if use_rrf:
            candidates = self._retrieve_with_rrf(
                processed_query, top_k_retrieve, top_k_fused=top_k_retrieve, debug=debug
            )
        else:
            candidates = self.multi_retriever.retrieve(processed_query, top_k=top_k_retrieve)
        timing["retrieval_rrf"] = round(time.time() - t0, 2)
        
        logger.info(f"   检索返回 {len(candidates)} 个候选")
        
        if not candidates:
            timing["total"] = round(time.time() - t_total_start, 2)
            return RAGResult(
                answer="抱歉，在知识库中未找到与您问题相关的内容。请尝试换一种问法或确认知识库已建立索引。",
                evidence=[],
                query=query,
                timing=timing
            )
        
        # Step 3: LLM Re-Ranking OR Simple Selection
        t0 = time.time()
        if use_llm_rerank:
            reranked = self.reranker.rerank(processed_query, candidates, top_k=top_k_rerank)
            logger.info(f"   LLM Re-Ranking 后保留 {len(reranked)} 个 chunk")
        else:
            reranked = candidates[:top_k_rerank]
            logger.info(f"   Simple Selection (No LLM Rerank) 保留 {len(reranked)} 个 chunk")
        timing["reranking"] = round(time.time() - t0, 2)
        
        # Step 4: 拼接 Evidence
        evidence_text = self._format_evidence(reranked)
        
        # Step 5: LLM Answer Generation（Grounded）
        t0 = time.time()
        answer = self._generate_answer(processed_query, evidence_text)
        timing["llm_generation"] = round(time.time() - t0, 2)
        
        timing["total"] = round(time.time() - t_total_start, 2)
        
        return RAGResult(
            answer=answer,
            evidence=reranked,
            query=query,
            timing=timing
        )
    
    def _retrieve_with_rrf(
        self,
        query: str,
        top_k_per_retriever: int = 15,
        top_k_fused: int = 15,
        debug: bool = False,
    ) -> List[RetrievedChunk]:
        """
        四路并行检索 + RRF 融合。

        分别调用 Dense、BM25、Section、SPLADE 四个检索器，
        收集各自的有序结果列表后使用 RRF 融合排序。

        Args:
            query: 处理后的查询
            top_k_per_retriever: 每个检索器返回的文档数
            top_k_fused: 融合后返回的文档总数
            debug: 是否打印调试信息

        Returns:
            RRF 融合后的 RetrievedChunk 列表
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        retrievers = [
            ("dense", self.dense_retriever),
            ("bm25", self.sparse_retriever),
            ("section", self.section_retriever),
            ("splade", self.splade_retriever),
        ]

        results_per_retriever: List[List[RetrievedChunk]] = []

        with ThreadPoolExecutor(max_workers=len(retrievers)) as executor:
            futures = {}
            for name, retriever in retrievers:
                future = executor.submit(retriever.retrieve, query, top_k_per_retriever)
                futures[future] = name

            # 按提交顺序收集（保持检索器顺序一致性）
            name_to_results: dict = {}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    name_to_results[name] = result
                    logger.info(f"   {name} 检索器返回 {len(result)} 个结果")
                except Exception as e:
                    logger.error(f"   {name} 检索失败: {e}")
                    name_to_results[name] = []

        # 按固定顺序排列（Dense, BM25, Section, SPLADE）
        for name, _ in retrievers:
            results_per_retriever.append(name_to_results.get(name, []))

        # 调试：打印各检索器 top3
        if debug:
            for (name, _), results in zip(retrievers, results_per_retriever):
                logger.info(f"[Debug] {name} Top-3:")
                for i, rc in enumerate(results[:3]):
                    logger.info(f"  {i+1}. {rc.chunk.chunk_id} | score={rc.score:.4f} | {rc.chunk.section}")

        # RRF 融合
        fused = reciprocal_rank_fusion(
            results_per_retriever,
            k=60,
            top_k=top_k_fused,
            debug=debug,
        )

        if debug:
            logger.info(f"[Debug] RRF 融合后 Top-5:")
            for i, rc in enumerate(fused[:5]):
                logger.info(
                    f"  {i+1}. {rc.chunk.chunk_id} | rrf={rc.score:.6f} | "
                    f"retrievers={rc.retriever_type} | {rc.chunk.section}"
                )

        return fused

    def _format_evidence(self, chunks: List[RetrievedChunk], max_chars_per_chunk: int = 0) -> str:
        """将检索到的 chunk 格式化为 evidence 文本
        
        Args:
            chunks: 检索结果
            max_chars_per_chunk: 每个 chunk 内容的最大字符数，0 表示不截断
        """
        parts = []
        for i, rc in enumerate(chunks):
            content = rc.chunk.content
            if max_chars_per_chunk > 0 and len(content) > max_chars_per_chunk:
                content = content[:max_chars_per_chunk] + "..."
            part = (
                f"--- 片段 {i+1} ---\n"
                f"来源: {rc.chunk.source}\n"
                f"章节: {rc.chunk.chapter}"
            )
            if rc.chunk.section:
                part += f" > {rc.chunk.section}"
            part += f"\n内容:\n{content}\n"
            parts.append(part)
        
        return "\n".join(parts)
    
    def _generate_answer(self, query: str, evidence: str) -> str:
        """调用 LLM 生成最终回答"""
        prompt = ANSWER_PROMPT_TEMPLATE.format(
            evidence=evidence,
            query=query
        )
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM 回答生成失败: {e}")
            return f"抱歉，生成回答时出错: {e}"
    
    def is_ready(self) -> bool:
        """检查 RAG 服务是否就绪（索引是否已建立）"""
        try:
            collections = [c.name for c in self.qdrant_client.get_collections().collections]
            has_qdrant = "rag_knowledge_chunks" in collections
            has_bm25 = len(self.sparse_retriever.chunks) > 0
            return has_qdrant and has_bm25
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 轻量 RAG 上下文检索（仅检索 + 融合 + 重排，不调 LLM 生成答案）
    # ------------------------------------------------------------------
    def retrieve_context(
        self,
        query: str,
        top_k_retrieve: int = 10,
        top_k_rerank: int = 5,
        use_query_rewrite: bool = True,
        use_rrf: bool = True,
    ) -> tuple:
        """
        只做检索，返回 (formatted_evidence, timing_dict)。

        供 Learning / General Agent 路径使用，将 RAG 知识注入
        LLM prompt，而非由 RAG 独立生成答案。

        Returns:
            (evidence_text: str, timing: dict)
        """
        timing: dict = {}
        t_total = time.time()

        # 1. Query Rewrite
        t0 = time.time()
        if use_query_rewrite:
            processed = rewrite_query(query)
        else:
            processed = query.strip()
        timing["query_rewrite"] = round(time.time() - t0, 2)

        # 2. 四路检索 + RRF
        t0 = time.time()
        if use_rrf:
            candidates = self._retrieve_with_rrf(processed, top_k_retrieve, top_k_fused=top_k_retrieve)
        else:
            candidates = self.multi_retriever.retrieve(processed, top_k=top_k_retrieve)
        timing["retrieval_rrf"] = round(time.time() - t0, 2)

        if not candidates:
            timing["total"] = round(time.time() - t_total, 2)
            return "", timing

        # 3. 简单截取（不走 LLM rerank，保证速度）
        top_chunks = candidates[:top_k_rerank]

        # 4. 格式化（取完整内容，不截断）
        evidence = self._format_evidence(top_chunks)
        timing["total"] = round(time.time() - t_total, 2)
        return evidence, timing
