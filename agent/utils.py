import random
import time
import requests
from bs4 import BeautifulSoup
from config import logger


def crawl_with_requests(url, selector, is_deep=False):
    """根据url和selector爬取页面内容

    Args:
        url (str): 要爬取的网页URL
        selector (str): CSS选择器，用于定位要提取的内容
        is_deep (bool): 是否深度爬取
            - False: 只获取当前selector下的直接文本内容
            - True: 获取当前selector下的所有内容，包括子节点

    Returns:
        list: 匹配选择器的元素内容列表，如果失败返回空列表
    """
    try:
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        # 添加随机延迟，避免被反爬
        time.sleep(random.uniform(1, 3))

        # 发送GET请求
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查HTTP状态码

        # 设置编码
        response.encoding = response.apparent_encoding

        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 根据选择器查找元素
        elements = soup.select(selector)

        # 提取元素内容
        results = []
        for element in elements:
            if is_deep:
                # 深度模式：获取所有内容，包括子节点
                text = element.get_text(strip=True)
            else:
                # 浅度模式：只获取直接文本内容，不包含子节点
                direct_texts = element.find_all(text=True, recursive=False)
                text = ''.join(str(t) for t in direct_texts).strip()

            if text:  # 只添加非空内容
                results.append(text)

        return results
    except requests.exceptions.RequestException as e:
        logger.error(f"请求错误: {e}")
        return []
    except Exception as e:
        logger.error(f"爬取过程中出现错误: {e}")
        return []


def crawl_with_requests_single(url, selector):
    """根据url和selector爬取页面内容，返回第一个匹配的元素

    Args:
        url (str): 要爬取的网页URL
        selector (str): CSS选择器，用于定位要提取的内容

    Returns:
        str: 第一个匹配选择器的元素内容，如果失败返回空字符串
    """
    results = crawl_with_requests(url, selector)
    return results[0] if results else ""
