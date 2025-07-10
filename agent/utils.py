from agent.third_part.minio import MinioClient
import urllib.parse
import os
import shutil
import uuid
from config import conf
from contextlib import contextmanager
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


@contextmanager
def temp_dir():
    temp_dir = conf.get_path("temp_dir")
    temp_dir_path = os.path.join(temp_dir, str(uuid.uuid4()))
    os.makedirs(temp_dir_path, exist_ok=True)
    yield temp_dir_path
    #  会递归地删除目录及其所有内容
    shutil.rmtree(temp_dir_path)


def get_url_data(url):
    """
    根据url获取数据，如果是本地文件，则返回文件内容，如果是url则返回url内容
    """
    if judge_file_local_or_url(url) == "url":
        return requests.get(url).content
    elif judge_file_local_or_url(url) == "local":
        return open(url, "rb").read()
    else:
        raise ValueError(f"Invalid file path: {url}")


def judge_file_local_or_url(file_path):
    parsed_url = urllib.parse.urlparse(file_path)
    if parsed_url.scheme in ['http', 'https', 'ftp', 'file']:
        return "url"
    elif os.path.isfile(file_path):
        return "local"
    else:
        raise ValueError(f"Invalid file path: {file_path}")


# 如何判断是本地文件还是url,假如是本地文件，判断文件是否存在。假如是url则下载到download_dir下
def judge_file_exist(file_path, download_dir, download_name):
    result = {"type": None, "exist": False, "path": file_path}

    # 判断是否是 URL
    parsed_url = urllib.parse.urlparse(file_path)
    if parsed_url.scheme in ["http", "https", "ftp"]:  # 判断是否为有效的 URL
        result["type"] = "url"
        # 下载文件到指定目录
        try:
            # 提取文件名
            # filename = os.path.basename(parsed_url.path)
            download_path = os.path.join(download_dir, file_path)

            # 下载文件
            response = requests.get(file_path, stream=True)
            if response.status_code == 200:
                with open(download_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                result["exist"] = True
                result["path"] = download_path
            else:
                result["exist"] = False
                result["path"] = None
        except Exception as e:
            result["exist"] = False
            result["path"] = None
            print(f"Error downloading file: {e}")

    # 判断是否是本地文件
    elif os.path.exists(file_path):
        result["type"] = "local"
        result["exist"] = True
        result["path"] = file_path
    else:
        result["type"] = "local"
        result["exist"] = False
        result["path"] = None

    return result
