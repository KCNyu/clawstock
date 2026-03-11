#!/usr/bin/env python3
"""
API 自动重试包装器
处理临时性 API 错误，包括 401 认证失败
"""

import time
import requests
from functools import wraps
from typing import Callable, Any, Optional
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class APIRetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        retry_on_401: bool = True,  # 是否对 401 错误重试
        retry_on_429: bool = True,  # 是否对 429 (速率限制) 重试
        retry_on_5xx: bool = True,  # 是否对 5xx 服务器错误重试
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.retry_on_401 = retry_on_401
        self.retry_on_429 = retry_on_429
        self.retry_on_5xx = retry_on_5xx


def should_retry(status_code: int, config: APIRetryConfig) -> bool:
    """判断是否应该重试"""
    if status_code == 401 and config.retry_on_401:
        return True
    if status_code == 429 and config.retry_on_429:
        return True
    if 500 <= status_code < 600 and config.retry_on_5xx:
        return True
    return False


def calculate_delay(attempt: int, config: APIRetryConfig) -> float:
    """计算重试延迟（指数退避）"""
    delay = config.initial_delay * (config.exponential_base ** attempt)
    return min(delay, config.max_delay)


def retry_api_call(config: Optional[APIRetryConfig] = None):
    """
    API 调用重试装饰器
    
    使用方法：
    @retry_api_call()
    def my_api_function():
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    """
    if config is None:
        config = APIRetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code if e.response else 0
                    last_exception = e
                    
                    # 判断是否应该重试
                    if attempt < config.max_retries and should_retry(status_code, config):
                        delay = calculate_delay(attempt, config)
                        
                        logger.warning(
                            f"API 调用失败 (HTTP {status_code}): {str(e)}\n"
                            f"第 {attempt + 1}/{config.max_retries} 次重试，"
                            f"等待 {delay:.1f} 秒..."
                        )
                        
                        time.sleep(delay)
                        continue
                    else:
                        # 不应该重试或已达到最大重试次数
                        logger.error(
                            f"API 调用最终失败 (HTTP {status_code}): {str(e)}"
                        )
                        raise
                
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    
                    # 对于网络错误，也进行重试
                    if attempt < config.max_retries:
                        delay = calculate_delay(attempt, config)
                        
                        logger.warning(
                            f"网络错误: {str(e)}\n"
                            f"第 {attempt + 1}/{config.max_retries} 次重试，"
                            f"等待 {delay:.1f} 秒..."
                        )
                        
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"网络请求最终失败: {str(e)}")
                        raise
                
                except Exception as e:
                    # 其他异常不重试
                    logger.error(f"未预期的错误: {str(e)}")
                    raise
            
            # 如果所有重试都失败了
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


# 使用示例
if __name__ == '__main__':
    # 示例 1：默认配置
    @retry_api_call()
    def fetch_stock_data(ticker: str):
        """获取股票数据（带自动重试）"""
        url = f"https://api.example.com/stock/{ticker}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    
    # 示例 2：自定义配置
    custom_config = APIRetryConfig(
        max_retries=5,
        initial_delay=2.0,
        retry_on_401=True,  # 对 401 错误重试
    )
    
    @retry_api_call(config=custom_config)
    def fetch_with_custom_retry(url: str):
        """使用自定义重试配置"""
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    
    # 测试
    print("API 重试包装器已加载")
    print("使用方法：")
    print("  from api_retry_wrapper import retry_api_call, APIRetryConfig")
    print("  @retry_api_call()")
    print("  def your_function():")
    print("      # your API call here")
