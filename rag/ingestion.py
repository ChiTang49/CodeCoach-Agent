"""
PDF 文档预处理模块
将 PDF 文件解析为结构化的 KnowledgeChunk 列表
支持章节/小节切分、chunk 分割和 metadata 生成
"""
import os
import re
import hashlib
from typing import List, Tuple, Optional
from pathlib import Path

import fitz  # PyMuPDF
import jieba

from rag.models import KnowledgeChunk


# ========================
# 配置常量
# ========================
CHUNK_MAX_CHARS = 800       # 每个 chunk 最大字符数 (~300-500 tokens 中文)
CHUNK_OVERLAP_CHARS = 100   # chunk 之间的重叠字符数
MIN_CHUNK_CHARS = 50        # 最小 chunk 字符数（过短的丢弃）


def _generate_chunk_id(source: str, chapter: str, section: str, idx: int) -> str:
    """生成唯一的 chunk ID"""
    raw = f"{source}::{chapter}::{section}::{idx}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def _extract_keywords(text: str, top_k: int = 8) -> List[str]:
    """
    使用 jieba 提取关键词
    """
    import jieba.analyse
    keywords = jieba.analyse.extract_tags(text, topK=top_k)
    return keywords


def _is_chapter_heading(line: str) -> bool:
    """判断是否为章节标题（一级标题）"""
    line = line.strip()
    # 匹配中文数字章节: 第一章、第二章 等
    if re.match(r'^第[一二三四五六七八九十百千\d]+[章篇]', line):
        return True
    # 匹配阿拉伯数字一级标题: 1. xxx, 1 xxx
    if re.match(r'^\d{1,2}[\.\s]\s*\S', line) and len(line) < 60:
        return True
    # 匹配全大写英文或重要关键词开头（OI-wiki 风格）
    if re.match(r'^[A-Z][A-Za-z\s\-]+$', line) and len(line) < 80:
        return True
    # 匹配特定大标题模式
    if re.match(r'^(基础|搜索|动态规划|字符串|数学|数据结构|图论|杂项|几何|语言基础|竞赛)', line) and len(line) < 40:
        return True
    return False


def _is_section_heading(line: str) -> bool:
    """判断是否为小节标题（二级及以下标题）"""
    line = line.strip()
    # 匹配 1.1 xxx, 1.2.3 xxx 等多级编号
    if re.match(r'^\d{1,2}\.\d{1,2}', line) and len(line) < 80:
        return True
    # 匹配中文"第X节"
    if re.match(r'^第[一二三四五六七八九十\d]+[节]', line):
        return True
    # 匹配简短标题行（通常是加粗标题被提取后的纯文本）
    if len(line) < 50 and not line.endswith('。') and not line.endswith('；') and len(line) > 2:
        # 含有中文且不含标点过多
        if re.search(r'[\u4e00-\u9fff]', line) and line.count('，') == 0 and line.count('。') == 0:
            # 再检查是否可能是小节标题（不以数字或符号结尾）
            if not re.search(r'[\d\.\,\;\:\!]$', line):
                return False  # 保守策略，不轻易判定
    return False


def _split_text_into_chunks(
    text: str,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap: int = CHUNK_OVERLAP_CHARS
) -> List[str]:
    """
    将长文本切分成固定大小的 chunk，支持重叠
    优先在段落边界处切分
    """
    if len(text) <= max_chars:
        return [text] if len(text) >= MIN_CHUNK_CHARS else []

    chunks = []
    # 先按段落分
    paragraphs = re.split(r'\n{2,}', text)
    
    current_chunk = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 如果当前段落本身就很长，需要进一步切分
        if len(para) > max_chars:
            # 先把当前 chunk 保存
            if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
                chunks.append(current_chunk.strip())
                current_chunk = ""
            
            # 按句子切分长段落
            sentences = re.split(r'(?<=[。！？\.\!\?])', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if len(current_chunk) + len(sent) <= max_chars:
                    current_chunk += sent
                else:
                    if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
                        chunks.append(current_chunk.strip())
                    # 保留重叠
                    if overlap > 0 and current_chunk:
                        current_chunk = current_chunk[-overlap:] + sent
                    else:
                        current_chunk = sent
        else:
            if len(current_chunk) + len(para) + 1 <= max_chars:
                current_chunk += "\n" + para if current_chunk else para
            else:
                if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
                    chunks.append(current_chunk.strip())
                # 保留重叠
                if overlap > 0 and current_chunk:
                    current_chunk = current_chunk[-overlap:] + "\n" + para
                else:
                    current_chunk = para

    if current_chunk and len(current_chunk) >= MIN_CHUNK_CHARS:
        chunks.append(current_chunk.strip())

    return chunks


def parse_pdf(pdf_path: str, source_name: Optional[str] = None) -> List[KnowledgeChunk]:
    """
    解析 PDF 文件为 KnowledgeChunk 列表
    
    Args:
        pdf_path: PDF 文件路径
        source_name: 来源名称（默认使用文件名）
    
    Returns:
        KnowledgeChunk 列表
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
    
    source = source_name or pdf_path.name
    print(f"📄 开始解析 PDF: {source}")
    
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    print(f"   总页数: {total_pages}")
    
    # 第一步：提取所有页面文本
    all_text = []
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            all_text.append(text)
    
    full_text = "\n".join(all_text)
    doc.close()
    print(f"   提取文本长度: {len(full_text)} 字符")
    
    # 第二步：按章节分割文本
    sections = _split_into_sections(full_text)
    print(f"   识别到 {len(sections)} 个章节/小节")
    
    # 第三步：对每个 section 进行 chunk 切分
    chunks = []
    chunk_idx = 0
    for chapter, section, section_text in sections:
        text_chunks = _split_text_into_chunks(section_text)
        for text in text_chunks:
            keywords = _extract_keywords(text)
            chunk = KnowledgeChunk(
                chunk_id=_generate_chunk_id(source, chapter, section, chunk_idx),
                content=text,
                source=source,
                chapter=chapter,
                section=section,
                keywords=keywords
            )
            chunks.append(chunk)
            chunk_idx += 1
    
    print(f"✅ 解析完成，共生成 {len(chunks)} 个 chunk")
    return chunks


def _split_into_sections(text: str) -> List[Tuple[str, str, str]]:
    """
    将全文按章节/小节标题分割
    
    Returns:
        [(chapter, section, text), ...]
    """
    lines = text.split('\n')
    sections = []
    
    current_chapter = "未分类"
    current_section = ""
    current_text_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_text_lines.append("")
            continue
        
        if _is_chapter_heading(stripped):
            # 保存之前的 section
            if current_text_lines:
                section_text = "\n".join(current_text_lines).strip()
                if section_text and len(section_text) >= MIN_CHUNK_CHARS:
                    sections.append((current_chapter, current_section, section_text))
            current_chapter = stripped[:60]  # 截取标题
            current_section = ""
            current_text_lines = []
        elif _is_section_heading(stripped):
            # 保存之前的 section
            if current_text_lines:
                section_text = "\n".join(current_text_lines).strip()
                if section_text and len(section_text) >= MIN_CHUNK_CHARS:
                    sections.append((current_chapter, current_section, section_text))
            current_section = stripped[:60]
            current_text_lines = []
        else:
            current_text_lines.append(line)
    
    # 保存最后一个 section
    if current_text_lines:
        section_text = "\n".join(current_text_lines).strip()
        if section_text and len(section_text) >= MIN_CHUNK_CHARS:
            sections.append((current_chapter, current_section, section_text))
    
    # 如果没有识别到任何章节结构，将全文作为一个 section
    if not sections:
        sections = [("未分类", "", text)]
    
    return sections
