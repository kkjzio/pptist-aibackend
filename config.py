"""
配置管理模块
"""
import os
from typing import Optional

class Settings:
    """应用配置类"""
    
    def __init__(self):
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.default_model: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        self.default_temperature: float = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        if not self.openai_api_key:
            return False
        if self.openai_api_key == "your-openai-api-key-here":
            return False
        # 检查是否为有效的 API Key 格式
        if not self.openai_api_key.startswith(('sk-', 'sk_')):
            return False
        return True
    
    def get_model_config(self, model_name: Optional[str] = None) -> dict:
        """获取模型配置"""
        return {
            "model": model_name or self.default_model,
            "temperature": self.default_temperature,
            "openai_api_key": self.openai_api_key,
            "openai_api_base": self.openai_base_url
        }


# 全局配置实例
settings = Settings()