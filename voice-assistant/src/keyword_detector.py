"""
关键词检测模块 - 纯业务逻辑（无外部依赖）

特点：
- 不依赖任何外部库
- 纯Python逻辑实现
- 可以直接测试，无需mock
"""

from typing import Optional, Tuple


class KeywordDetector:
    """关键词检测器 - 纯业务逻辑"""
    
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
        """初始化关键词检测器"""
        self.keywords = keywords or self.DEFAULT_KEYWORDS
        self.keyword_groups = keyword_groups or self.DEFAULT_KEYWORD_GROUPS
    
    def get_keyword_category(self, keyword: str) -> Optional[str]:
        """获取关键词所属类别"""
        for category, keywords in self.keyword_groups.items():
            if keyword in keywords:
                return category
        return None
    
    def detect(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """检测文本中的关键词并提取命令"""
        if not text or not text.strip():
            return False, None, None
        
        text = text.strip()
        
        for keyword in self.keywords:
            if keyword in text:
                param = self._extract_parameter(text, keyword)
                return True, keyword, param
        
        return False, None, None
    
    def _extract_parameter(self, text: str, keyword: str) -> str:
        """提取命令参数"""
        import re
        
        try:
            parts = text.split(keyword, 1)
            if len(parts) > 1:
                param = parts[1].strip()
            else:
                param = ""
            
            param = re.sub(r'[^\w\s\-\.\/\\]', '', param)
            param = param.strip()
            
            return param
            
        except Exception:
            return ""
    
    def is_valid_command(self, keyword: str, param: str) -> bool:
        """验证命令是否有效"""
        import re
        
        if keyword not in self.keywords:
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
                return False
        
        return True
    
    def format_command(self, keyword: str, param: str) -> str:
        """格式化为opencode命令"""
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
    
    def remove_keyword(self, keyword: str) -> bool:
        """移除关键词"""
        if keyword in self.keywords:
            self.keywords.remove(keyword)
            return True
        return False