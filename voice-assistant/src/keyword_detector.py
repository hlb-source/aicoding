"""
关键词检测模块 - 从语音文本中提取命令

功能：
- 关键词白名单过滤
- 命令提取和解析
- 安全验证
"""

import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class KeywordDetector:
    """关键词检测器 - 从文本中提取命令"""
    
    DEFAULT_KEYWORDS = [
        "创建",
        "读取",
        "编辑",
        "删除",
        "运行",
        "写代码",
        "搜索",
        "显示",
        "查找",
        "修改",
        "添加",
        "移除",
        "执行",
        "测试"
    ]
    
    def __init__(self, keywords: Optional[list] = None):
        """
        初始化关键词检测器
        
        Args:
            keywords: 关键词列表（None使用默认列表）
        """
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        logger.info(f"关键词检测器初始化: {len(self.keywords)}个关键词")
    
    def detect(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        检测文本中的关键词并提取命令
        
        Args:
            text: 输入文本
            
        Returns:
            (是否检测到关键词, 关键词, 命令参数)
        """
        if not text or not text.strip():
            return False, None, None
        
        text = text.strip()
        logger.debug(f"检测文本: {text}")
        
        for keyword in self.keywords:
            if keyword in text:
                param = self._extract_parameter(text, keyword)
                logger.info(f"检测到关键词: {keyword}, 参数: {param}")
                return True, keyword, param
        
        logger.debug("未检测到关键词")
        return False, None, None
    
    def _extract_parameter(self, text: str, keyword: str) -> str:
        """
        提取命令参数
        
        Args:
            text: 输入文本
            keyword: 关键词
            
        Returns:
            提取的参数
        """
        try:
            parts = text.split(keyword, 1)
            if len(parts) > 1:
                param = parts[1].strip()
            else:
                param = ""
            
            param = re.sub(r'[^\w\s\-\.\/\\]', '', param)
            param = param.strip()
            
            return param
            
        except Exception as e:
            logger.warning(f"参数提取失败: {e}")
            return ""
    
    def is_valid_command(self, keyword: str, param: str) -> bool:
        """
        验证命令是否有效
        
        Args:
            keyword: 关键词
            param: 参数
            
        Returns:
            是否有效
        """
        if keyword not in self.keywords:
            logger.warning(f"无效关键词: {keyword}")
            return False
        
        dangerous_patterns = [
            r'[;&|`$]',
            r'\.\.\/',
            r'~\/',
            r'>',
            r'<',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, param):
                logger.warning(f"检测到危险模式: {pattern}")
                return False
        
        return True
    
    def format_command(self, keyword: str, param: str) -> str:
        """
        格式化为opencode命令
        
        Args:
            keyword: 关键词
            param: 参数
            
        Returns:
            格式化的命令字符串
        """
        if not param:
            return f"{keyword}"
        
        return f"{keyword} {param}"
    
    def get_keywords(self) -> list:
        """获取当前关键词列表"""
        return self.keywords.copy()
    
    def add_keyword(self, keyword: str) -> None:
        """添加关键词"""
        if keyword and keyword not in self.keywords:
            self.keywords.append(keyword)
            logger.info(f"添加关键词: {keyword}")
    
    def remove_keyword(self, keyword: str) -> bool:
        """移除关键词"""
        if keyword in self.keywords:
            self.keywords.remove(keyword)
            logger.info(f"移除关键词: {keyword}")
            return True
        return False