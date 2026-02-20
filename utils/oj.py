"""
在线评测模块（Online Judge）
使用本地 subprocess 执行代码并返回评测结果
"""
import os
import subprocess
import tempfile
import time
from typing import Optional, Tuple
from models import SubmissionResult


class OnlineJudge:
    """
    在线评测系统，支持 Python 代码的本地评测
    """
    
    def __init__(self, timeout: int = 5):
        """
        初始化评测系统
        
        Args:
            timeout: 代码执行超时时间（秒）
        """
        self.timeout = timeout
    
    def evaluate_python(
        self,
        problem_id: int,
        code: str,
        test_cases: list = None
    ) -> SubmissionResult:
        """
        评测 Python 代码
        
        Args:
            problem_id: 题目 ID
            code: 用户提交的代码
            test_cases: 测试用例列表，格式：[(input, expected_output), ...]
            
        Returns:
            评测结果
        """
        # 如果没有提供测试用例，返回默认结果
        if not test_cases:
            return SubmissionResult(
                problem_id=problem_id,
                status="NO_TEST",
                error_message="暂无测试用例"
            )
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            start_time = time.time()
            
            # 遍历测试用例
            for idx, (test_input, expected_output) in enumerate(test_cases):
                result = self._run_test_case(temp_file, test_input, expected_output)
                
                if result.status != "AC":
                    return result
            
            # 所有测试用例通过
            elapsed_time = int((time.time() - start_time) * 1000)
            return SubmissionResult(
                problem_id=problem_id,
                status="AC",
                runtime_ms=elapsed_time
            )
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _run_test_case(
        self,
        code_file: str,
        test_input: str,
        expected_output: str
    ) -> SubmissionResult:
        """
        运行单个测试用例
        
        Args:
            code_file: 代码文件路径
            test_input: 测试输入
            expected_output: 期望输出
            
        Returns:
            评测结果
        """
        try:
            # 执行代码
            result = subprocess.run(
                ['python', code_file],
                input=test_input,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # 检查是否有运行时错误
            if result.returncode != 0:
                return SubmissionResult(
                    problem_id=0,
                    status="RE",
                    error_message=result.stderr.strip()
                )
            
            # 比较输出
            actual_output = result.stdout.strip()
            expected = expected_output.strip()
            
            if actual_output == expected:
                return SubmissionResult(problem_id=0, status="AC")
            else:
                return SubmissionResult(
                    problem_id=0,
                    status="WA",
                    error_message=f"期望输出: {expected}\n实际输出: {actual_output}"
                )
                
        except subprocess.TimeoutExpired:
            return SubmissionResult(
                problem_id=0,
                status="TLE",
                error_message=f"代码执行超时（>{self.timeout}秒）"
            )
        except Exception as e:
            return SubmissionResult(
                problem_id=0,
                status="ERROR",
                error_message=str(e)
            )


# 预定义的测试用例示例
SAMPLE_TEST_CASES = {
    "two_sum": [
        ("[2,7,11,15]\n9", "[0,1]"),
        ("[3,2,4]\n6", "[1,2]"),
    ],
    "add_two_numbers": [
        ("2 -> 4 -> 3\n5 -> 6 -> 4", "7 -> 0 -> 8"),
    ],
}
