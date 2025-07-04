import random
import time
import requests
from bs4 import BeautifulSoup
from agent.selector import selectors
from selenium.webdriver.chrome.options import Options
from crawl4ai import BrowserConfig
from config import logger
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai import CrawlerRunConfig
from crawl4ai import AsyncWebCrawler
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re


def capitalize_title(title: str) -> str:
    """
    将标题中每个词的首个字符大写
    处理特殊情况：保持某些词的小写（如 of, and, the 等介词和冠词）
    """
    # 定义不需要大写的词（介词、冠词、连词等）
    lowercase_words = {'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if',
                       'in', 'is', 'it', 'of', 'on', 'or', 'the', 'to', 'up', 'with', 'yet'}

    # 分割标题为单词
    words = title.split()
    capitalized_words = []

    for i, word in enumerate(words):
        # 清理单词（去除标点符号）
        clean_word = ''.join(c for c in word if c.isalnum())

        # 如果是第一个词或最后一个词，或者不在小写词列表中，或者长度大于3，则大写
        if (i == 0 or i == len(words) - 1 or
            clean_word.lower() not in lowercase_words or
                len(clean_word) > 3):  # 长度大于3的词通常需要大写
            # 大写第一个字符，保持其他字符不变
            if word:
                capitalized_word = word[0].upper(
                ) + word[1:] if len(word) > 0 else word
                capitalized_words.append(capitalized_word)
            else:
                capitalized_words.append(word)
        else:
            # 保持小写
            capitalized_words.append(word)

    return ' '.join(capitalized_words)


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


def get_best_selling_competing_products_url(product_title, platform="lazada"):
    """
    根据商品标题获取最佳销售竞品
    通过关键词工具 ，反查竞品流量词
    """
    pass


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


def search_competitors(url, platform="lazada", max_products=10):
    """
    根据商品URL提取标题并搜索竞品
    Args:
        url (str): 商品页面URL
        platform (str): 平台名称，默认lazada
        max_products (int): 最大返回商品数量
    Returns:
        list: 竞品链接列表
    """
    # 提取商品标题
    title_selector = selectors[platform]["product_title"]
    title = crawl_with_requests_single(url, title_selector)
    if not title:
        print("无法提取商品标题，无法继续搜索竞品")
        return []
    # 清理标题作为搜索词
    search_term = clean_title_for_search(title)
    if not search_term:
        print("标题清理后为空")
        return []
    # 步骤2: 使用Selenium在Lazada搜索框中搜索关键词
    competitor_urls = []
    try:
        # 配置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # ← 更稳定的 headless
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--remote-debugging-port=9222")  # ← 必须加上
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--no-zygote")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

        print("启动Selenium浏览器...")
        driver = webdriver.Chrome(options=chrome_options)
        # 访问Lazada首页
        lazada_base_url = "https://www.lazada.com.my/"
        print(f"访问Lazada首页: {lazada_base_url}")
        driver.get(lazada_base_url)
        # 等待搜索框加载
        wait = WebDriverWait(driver, 10)
        print("等待搜索框加载...")
        search_box = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input.search-box__input--O34g")))
        # 输入搜索关键词
        print(f"在搜索框中输入关键词: {search_term}")
        search_box.clear()
        search_box.send_keys(search_term)
        search_box.send_keys(Keys.RETURN)
        # 等待商品链接元素加
        print("等待商品链接元素加载...")
        wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "a[href*='/products/']")))

        # 提取商品链接元素
        print("提取搜索结果中的商品链接...")
        product_elements = driver.find_elements(
            By.CSS_SELECTOR, "a[href*='/products/']")
        # 如果找不到商品，尝试其他选择器
        if not product_elements:
            print("尝试备用商品选择器...")
            product_elements = driver.find_elements(
                By.CSS_SELECTOR, "div[data-tracking='product-card'] a[href*='/products/']")
        # 收集竞品URL（排除原始URL）
        count = 0
        for element in product_elements:
            product_url = element.get_attribute('href')
            # 检查URL是否为有效的商品链接
            if product_url and '/products/' in product_url and product_url != url:
                # 提取商品ID进行比较，避免重复
                current_id = re.search(r'/products/.-i(\d+)-', product_url)
                original_id = re.search(r'/products/.*-i(\d+)-', url)
                # 排除原始商品
                if (not original_id or not current_id or
                        (original_id and current_id and original_id.group(1) != current_id.group(1))):
                    competitor_urls.append(product_url)
                    count += 1
                    print(f"找到竞品 {count}: {product_url}")
                    if count >= max_products:
                        break
        print(f"总共找到 {len(competitor_urls)} 个竞品")
    except TimeoutException as e:
        print(f"等待超时: {e}")
    except NoSuchElementException as e:
        print(f"未找到元素: {e}")
    except Exception as e:
        print(f"Selenium搜索过程中出错: {e}")
    finally:
        try:
            driver.quit()
            print("Selenium浏览器已关闭")
        except:
            pass
    return competitor_urls
