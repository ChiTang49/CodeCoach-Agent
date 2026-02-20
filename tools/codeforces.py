"""
Codeforces 题目检索工具
负责根据标签和难度筛选题目，以及获取题面
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from urllib import parse, request
import zlib

from models import ProblemInfo


@dataclass
class CodeforcesProblem:
    """内部数据结构，统一处理 Codeforces 返回的题目数据"""

    contest_id: Optional[int]
    index: str
    name: str
    rating: Optional[int]
    tags: List[str]

    @property
    def link(self) -> str:
        """生成题目链接"""
        if self.contest_id:
            return f"https://codeforces.com/problemset/problem/{self.contest_id}/{self.index}"
        return "https://codeforces.com/problemset"

    def to_problem_info(self) -> ProblemInfo:
        """转换为系统统一的 ProblemInfo"""
        problem_id = self._compute_problem_id()
        difficulty = self._rating_to_difficulty()
        description = self._build_description()
        return ProblemInfo(
            id=problem_id,
            title=self.name,
            link=self.link,
            description=description,
            difficulty=difficulty,
            tags=self.tags,
        )

    def _rating_to_difficulty(self) -> Optional[str]:
        if self.rating is None:
            return None
        if self.rating < 1400:
            return "简单"
        if self.rating < 1800:
            return "中等"
        return "困难"

    def _build_description(self) -> str:
        rating_text = f"评级 {self.rating}" if self.rating else "评级未知"
        tag_text = ", ".join(self.tags) if self.tags else "未标注标签"
        return f"Codeforces 题目，{rating_text}，标签：{tag_text}"

    def _compute_problem_id(self) -> int:
        if self.contest_id is None:
            key = f"{self.name}:{self.index}".encode("utf-8")
            return zlib.crc32(key)

        index_value = 0
        for char in self.index.upper():
            if char.isdigit():
                index_value = index_value * 36 + int(char)
            elif "A" <= char <= "Z":
                index_value = index_value * 36 + (ord(char) - ord("A") + 10)
        return self.contest_id * 1000 + index_value


class CodeforcesProblemTool:
    """封装 Codeforces 题目检索逻辑的工具"""

    API_ENDPOINT = "https://codeforces.com/api/problemset.problems"

    DEFAULT_PROBLEMS: Dict[str, List[ProblemInfo]] = {
        "greedy": [
            ProblemInfo(
                id=1001001,
                title="Queue at the School",
                link="https://codeforces.com/problemset/problem/266/B",
                description="模拟简单的队列变换，体现局部交换的贪心策略",
                difficulty="简单",
                tags=["greedy", "implementation"],
            ),
            ProblemInfo(
                id=1001002,
                title="Theatre Square",
                link="https://codeforces.com/problemset/problem/1/A",
                description="计算最小铺砖数量，核心在于局部最优的取整策略",
                difficulty="简单",
                tags=["greedy", "math"],
            ),
            ProblemInfo(
                id=1001003,
                title="Activity Selection Simplified",
                link="https://codeforces.com/problemset/problem/1742/C",
                description="基于排序与优先选择的区间调度变体",
                difficulty="中等",
                tags=["greedy"],
            ),
        ],
        "dp": [
            ProblemInfo(
                id=1002001,
                title="Frog Jumps",
                link="https://codeforces.com/problemset/problem/1077/C",
                description="利用状态转移构造最优跳跃方案",
                difficulty="中等",
                tags=["dp"],
            ),
            ProblemInfo(
                id=1002002,
                title="Vasya and Books",
                link="https://codeforces.com/problemset/problem/1086/A",
                description="动态规划 + 枚举求最优策略",
                difficulty="中等",
                tags=["dp", "greedy"],
            ),
        ],
    }

    # 常见算法名称与 Codeforces 标签的映射表
    TAG_MAPPING: Dict[str, str] = {
        "动态规划": "dp",
        "背包": "knapsack",
        "二分": "binary search",
        "二分查找": "binary search",
        "贪心": "greedy",
        "图论": "graphs",
        "图": "graphs",
        "树": "trees",
        "深度优先": "dfs and similar",
        "广度优先": "dfs and similar",
        "搜索": "dfs and similar",
        "并查集": "dsu",
        "字符串": "strings",
        "数学": "math",
        "几何": "geometry",
        "排序": "sortings",
        "位运算": "bitmasks",
        "组合数学": "combinatorics",
        "概率": "probabilities",
        "数论": "number theory",
    }

    # 难度名称到评级区间的映射（包含中英文别名）
    DIFFICULTY_RANGES: Dict[str, Tuple[int, int]] = {
        "easy": (800, 1400),
        "简单": (800, 1400),
        "beginner": (800, 1400),
        "medium": (1400, 1800),
        "中等": (1400, 1800),
        "intermediate": (1400, 1800),
        "hard": (1800, 2400),
        "困难": (1800, 2400),
        "advanced": (1800, 2400),
    }

    def fetch_problems(
        self,
        tag: str,
        difficulty: str,
        limit: int = 3,
    ) -> List[ProblemInfo]:
        """根据标签和难度获取题目列表"""
        resolved_tag = self._resolve_tag(tag)
        min_rating, max_rating = self._resolve_difficulty(difficulty)

        problems: List[CodeforcesProblem] = []
        try:
            problems = self._request_problems(resolved_tag)
        except RuntimeError as exc:
            print(exc)

        filtered = self._collect_within_limits(problems, min_rating, max_rating, limit)

        if not filtered and problems:
            relaxed_min = max(0, min_rating - 200)
            relaxed_max = max_rating + 400
            relaxed = self._collect_within_limits(
                problems,
                relaxed_min,
                relaxed_max,
                limit,
                include_unrated=True,
            )
            if relaxed:
                return relaxed

        if not filtered:
            fallback = self._fallback_from_defaults(resolved_tag, limit)
            if fallback:
                return fallback

        return filtered

    def _resolve_tag(self, tag: str) -> str:
        if not tag:
            return "implementation"

        normalized = tag.strip().lower()
        for key, mapped_tag in self.TAG_MAPPING.items():
            if key in tag:
                return mapped_tag
            if key in normalized:
                return mapped_tag
        return normalized or "implementation"

    def _resolve_difficulty(self, difficulty: str) -> Tuple[int, int]:
        if not difficulty:
            return (800, 1800)

        normalized = difficulty.strip().lower()
        return self.DIFFICULTY_RANGES.get(normalized, (800, 1800))

    def _request_problems(self, tag: str) -> List[CodeforcesProblem]:
        query = parse.urlencode({"tags": tag}) if tag else ""
        url = f"{self.API_ENDPOINT}?{query}" if query else self.API_ENDPOINT

        try:
            with request.urlopen(url, timeout=6) as response:
                payload = json.load(response)
        except Exception as exc:
            raise RuntimeError(f"获取 Codeforces 题目失败: {exc}")

        if payload.get("status") != "OK":
            raise RuntimeError(f"Codeforces API 返回错误: {payload.get('comment', '未知错误')}")

        problems_data = payload.get("result", {}).get("problems", [])
        problems: List[CodeforcesProblem] = []
        for item in problems_data:
            contest_id = item.get("contestId")
            index = item.get("index")
            name = item.get("name")
            rating = item.get("rating")
            tags = item.get("tags", [])

            if not index or not name:
                continue

            problems.append(
                CodeforcesProblem(
                    contest_id=contest_id,
                    index=index,
                    name=name,
                    rating=rating,
                    tags=tags,
                )
            )

        return problems

    def _collect_within_limits(
        self,
        problems: Iterable[CodeforcesProblem],
        min_rating: int,
        max_rating: int,
        limit: int,
        include_unrated: bool = False,
    ) -> List[ProblemInfo]:
        collected: List[ProblemInfo] = []
        for problem in self._filter_by_difficulty(problems, min_rating, max_rating, include_unrated):
            collected.append(problem.to_problem_info())
            if len(collected) >= limit:
                break
        return collected

    def _filter_by_difficulty(
        self,
        problems: Iterable[CodeforcesProblem],
        min_rating: int,
        max_rating: int,
        include_unrated: bool = False,
    ) -> Iterable[CodeforcesProblem]:
        for problem in problems:
            # 没有评级的题目直接跳过，避免推荐不确定难度
            if problem.rating is None:
                if include_unrated:
                    yield problem
                continue
            if min_rating <= problem.rating <= max_rating:
                yield problem

    def _fallback_from_defaults(self, resolved_tag: str, limit: int) -> List[ProblemInfo]:
        if resolved_tag in self.DEFAULT_PROBLEMS:
            return self.DEFAULT_PROBLEMS[resolved_tag][:limit]
        # 若未命中具体标签，尝试使用通用贪心题库
        generic = self.DEFAULT_PROBLEMS.get("greedy", [])
        return generic[:limit] if generic else []


class CodeforcesProblemFetcher:
    """获取Codeforces题目详细信息（题面）"""
    
    @staticmethod
    def parse_problem_url(url: str) -> Optional[Tuple[str, str]]:
        """
        解析Codeforces题目URL，提取contest_id和problem_index
        支持格式：
        - https://codeforces.com/problemset/problem/2184/C
        - https://codeforces.com/contest/2184/problem/C
        """
        patterns = [
            r'codeforces\.com/problemset/problem/(\d+)/([A-Z]\d*)',
            r'codeforces\.com/contest/(\d+)/problem/([A-Z]\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1), match.group(2)
        return None
    
    @staticmethod
    def fetch_problem_statement(contest_id: str, problem_index: str) -> Optional[Dict[str, str]]:
        """
        获取题面信息
        返回：{
            'title': 题目标题,
            'time_limit': 时间限制,
            'memory_limit': 内存限制,
            'statement': 题目描述（简化版）,
            'input': 输入格式,
            'output': 输出格式,
            'link': 题目链接
        }
        """
        url = f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
        
        try:
            # 设置User-Agent避免被拒绝
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = request.Request(url, headers=headers)
            
            with request.urlopen(req, timeout=8) as response:
                html = response.read().decode('utf-8')
            
            # 简单的文本提取（不使用BeautifulSoup，避免依赖）
            problem_data = {
                'link': url,
                'contest_id': contest_id,
                'problem_index': problem_index
            }
            
            # 提取标题
            title_match = re.search(r'<div class="title">([^<]+)</div>', html)
            if title_match:
                problem_data['title'] = title_match.group(1).strip()
            
            # 提取时间限制
            time_match = re.search(r'<div class="time-limit">.*?(\d+)\s*second', html, re.DOTALL)
            if time_match:
                problem_data['time_limit'] = f"{time_match.group(1)}秒"
            
            # 提取内存限制
            memory_match = re.search(r'<div class="memory-limit">.*?(\d+)\s*megabyte', html, re.DOTALL)
            if memory_match:
                problem_data['memory_limit'] = f"{memory_match.group(1)}MB"
            
            # 提取题目描述（获取problem-statement部分）
            statement_match = re.search(
                r'<div class="problem-statement">(.+?)</div>\s*<div class="input-specification">',
                html,
                re.DOTALL
            )
            if statement_match:
                statement_html = statement_match.group(1)
                # 移除HTML标签，保留文本
                statement_text = re.sub(r'<[^>]+>', ' ', statement_html)
                statement_text = re.sub(r'\s+', ' ', statement_text).strip()
                problem_data['statement'] = statement_text[:800] + '...' if len(statement_text) > 800 else statement_text
            
            # 提取输入格式
            input_match = re.search(
                r'<div class="input-specification">(.+?)</div>',
                html,
                re.DOTALL
            )
            if input_match:
                input_html = input_match.group(1)
                input_text = re.sub(r'<[^>]+>', ' ', input_html)
                input_text = re.sub(r'\s+', ' ', input_text).strip()
                problem_data['input'] = input_text[:400] + '...' if len(input_text) > 400 else input_text
            
            # 提取输出格式
            output_match = re.search(
                r'<div class="output-specification">(.+?)</div>',
                html,
                re.DOTALL
            )
            if output_match:
                output_html = output_match.group(1)
                output_text = re.sub(r'<[^>]+>', ' ', output_html)
                output_text = re.sub(r'\s+', ' ', output_text).strip()
                problem_data['output'] = output_text[:400] + '...' if len(output_text) > 400 else output_text
            
            return problem_data
            
        except Exception as e:
            print(f"获取题面失败: {e}")
            return None
    
    @classmethod
    def get_problem_from_url(cls, url: str) -> Optional[Dict[str, str]]:
        """
        从URL直接获取题面
        """
        parsed = cls.parse_problem_url(url)
        if not parsed:
            return None
        
        contest_id, problem_index = parsed
        return cls.fetch_problem_statement(contest_id, problem_index)

