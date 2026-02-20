"""
记忆工具封装
基于 hello-agents 的 MemoryTool 提供便捷的记忆操作
"""
from hello_agents.tools import MemoryTool


class MemoryManager:
    """
    记忆管理器，封装 MemoryTool 的常用操作
    """
    
    def __init__(self, user_id: str = "default_user"):
        """
        初始化记忆管理器
        
        Args:
            user_id: 用户唯一标识
        """
        self.user_id = user_id
        self.memory_tool = MemoryTool(user_id=user_id)
    
    def add_memory(self, content: str) -> str:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            
        Returns:
            操作结果
        """
        try:
            return self.memory_tool.execute("add", content=content)
        except Exception as e:
            print(f"添加记忆失败: {e}")
            return "添加失败"
    
    def search_memory(self, query: str, top_k: int = 3) -> str:
        """
        搜索记忆
        
        Args:
            query: 查询文本
            top_k: 返回的记忆数量
            
        Returns:
            搜索结果
        """
        try:
            return self.memory_tool.execute("search", query=query, top_k=top_k)
        except Exception as e:
            print(f"搜索记忆失败: {e}")
            return "未找到相关记忆"
    
    def get_summary(self) -> str:
        """
        获取记忆摘要
        
        Returns:
            记忆摘要
        """
        try:
            return self.memory_tool.execute("summary")
        except Exception as e:
            print(f"获取摘要失败: {e}")
            return "暂无记忆摘要"
    
    def clear_memory(self) -> str:
        """
        清空记忆（慎用）
        
        Returns:
            操作结果
        """
        try:
            return self.memory_tool.execute("clear")
        except Exception as e:
            print(f"清空记忆失败: {e}")
            return "清空失败"
