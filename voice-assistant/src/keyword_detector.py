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
    
    DEFAULT_KEYWORD_GROUPS = {
        "创建类": ["创建", "新建", "生成", "建立", "制作"],
        "读取类": ["读取", "打开", "查看", "显示", "浏览"],
        "编辑类": ["编辑", "修改", "更新", "改变", "调整"],
        "删除类": ["删除", "移除", "清除", "去掉", "卸载"],
        "执行类": ["运行", "执行", "启动", "调用", "触发"],
        "生成类": ["写代码", "生成代码", "编写", "编码", "实现"],
        "搜索类": ["搜索", "查找", "寻找", "定位", "检索"],
        "显示类": ["显示", "列出", "展示", "打印", "输出"],
        "测试类": ["测试", "调试", "验证", "检查"],
        "部署类": ["部署", "发布", "推送", "提交", "安装"],
    }
    
    DEFAULT_KEYWORDS = [
        "创建", "新建", "生成", "建立", "制作",
        "读取", "打开", "查看", "显示", "浏览",
        "编辑", "修改", "更新", "改变", "调整",
        "删除", "移除", "清除", "去掉", "卸载",
        "运行", "执行", "启动", "调用", "触发",
        "写代码", "生成代码", "编写", "编码", "实现",
        "搜索", "查找", "寻找", "定位", "检索",
        "列出", "展示", "打印", "输出",
        "测试", "调试", "验证", "检查",
        "部署", "发布", "推送", "提交", "安装",
    ]
    
    def __init__(self, keywords: Optional[list] = None, keyword_groups: Optional[dict] = None):
        """
        初始化关键词检测器
        
        Args:
            keywords: 关键词列表（None使用默认列表）
            keyword_groups: 关键词分组字典（None使用默认分组）
        """
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        self.keyword_groups = keyword_groups or self.DEFAULT_KEYWORD_GROUPS
        logger.info(f"关键词检测器初始化: {len(self.keywords)}个关键词, {len(self.keyword_groups)}个分组")
    
    def get_keyword_category(self, keyword: str) -> Optional[str]:
        """
        获取关键词所属类别
        
        Args:
            keyword: 关键词
            
        Returns:
            关键词类别（如"创建类"、"读取类"等）
        """
        for category, keywords in self.keyword_groups.items():
            if keyword in keywords:
                return category
        return None
    
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