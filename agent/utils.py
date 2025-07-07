import random
import time
import requests
from bs4 import BeautifulSoup
from agent.seo_agent.selector import selectors
from selenium.webdriver.chrome.options import Options
from config import logger
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai import AsyncWebCrawler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from crawl4ai import BrowserConfig
from crawl4ai import CrawlerRunConfig
import re


async def extracted_content_in_lazada_by_css_selector(url, css_schema):
    """
    css_schema参考schema = {
    "name": str,              # Schema name
    "baseSelector": str,      # Base CSS selector
    "fields": [               # List of fields to extract
        {
            "name": str,      # Field name
            "selector": str,  # CSS selector
            "type": str,     # Field type: "text", "attribute", "html", "regex"
            "attribute": str, # For type="attribute"
            "pattern": str,  # For type="regex"
            "transform": str, # Optional: "lowercase", "uppercase", "strip"
            "default": Any    # Default value if extraction fails
        }
        ]
    }
    """
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=True,
        # proxy="http://localhost:8888",

    )
    css_strategy = JsonCssExtractionStrategy(schema=css_schema)
    crawler_run_config = CrawlerRunConfig(
        # Force the crawler to wait until images are fully loaded
        wait_for_images=True,
        # Option 1: If you want to automatically scroll the page to load images
        scan_full_page=True,  # Tells the crawler to try scrolling the entire page
        scroll_delay=0.5,     # Delay (seconds) between scroll steps
        js_code="window.scrollTo(0, document.body.scrollHeight);",
        wait_for=css_schema["fields"][0]["selector"],
        # cache_mode=CacheMode.BYPASS,
        verbose=True,
        extraction_strategy=css_strategy,

    )
    crawler = AsyncWebCrawler(config=browser_config)
    result = await crawler.arun(url=url, config=crawler_run_config)
    return result.extracted_content


def clean_title_for_search(title):
    """清理商品标题用于搜索"""
    if not title:
        return ""
    import re
    # 移除常见无关词汇
    remove_words = [
        "lazada", "official", "store", "original", "genuine", "brand", "new",
        "hot", "sale", "promotion", "discount", "free", "shipping", "ready", "stock"
    ]
    # 转小写并移除特殊字符
    clean_title = re.sub(r'[^\w\s]', ' ', title.lower())
    clean_title = re.sub(r'\d+', '', clean_title)
    # 分词并过滤
    words = [w for w in clean_title.split(
    ) if w not in remove_words and len(w) > 2]
    # 返回前5个关键词
    return ' '.join(words[:5])


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


