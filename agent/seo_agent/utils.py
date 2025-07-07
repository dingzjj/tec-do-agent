from agent.utils import extracted_content_in_lazada_by_css_selector
from agent.llm import create_azure_llm
from agent.seo_agent.selector import selectors
import re
import json
import asyncio
from urllib.parse import quote_plus


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


async def search_competitors(url, platform="lazada", max_products=5):
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
    title_selector = selectors[platform]["title"]
    css_schema = {
        "baseSelector": "#container",
        "fields": [
            {"name": "title",
                "selector": title_selector,
             "type": "text"}
        ],
    }
    title = await extracted_content_in_lazada_by_css_selector(url, css_schema)
    print(f"提取到的商品标题: {title}")
    if not title:
        print("无法提取商品标题，无法继续搜索竞品")
        return []

    # 清理标题作为搜索词
    llm = create_azure_llm()
    prompt = f"""
            请从以下商品标题中提取最重要的3个关键词或短语，代表核心卖点。去除品牌词、型号、重复词和无关修饰词，输出为英文关键词列表：

            商品标题：
            "{title}"

            关键词列表：
            """
    response = await llm.ainvoke(prompt)
    print("提取关键词结果：")
    print(response.content)
    search_term = response.content.strip().splitlines()
    search_term = [kw.lstrip('- ').strip() for kw in search_term]
    print(f"清理后的搜索关键词: {search_term}")
    if not search_term:
        print("标题清理后为空")
        return []

    # 爬取 Lazada 竞品
    search_terms = " ".join(search_term)
    search_url = f"https://www.lazada.com.my/catalog/?q={
        quote_plus(search_terms)}"
    competitor_data = []

    css_schema = {
        "name": "lazada_product_list",
        "baseSelector": "div[data-qa-locator='product-item']",
        "fields": [
            {
                "name": "link",
                "selector": "a[href*='/products/']",
                "type": "attribute",
                "attribute": "href"
            },
            {
                "name": "sold",
                "selector": "span._1cEkb > span:first-child",
                "type": "text"
            }
        ]
    }

    try:
        extracted = await extracted_content_in_lazada_by_css_selector(search_url, css_schema)
        extracted = json.loads(extracted)

        original_id = re.search(r'/products/.*-i(\d+)', url)
        original_id = original_id.group(1) if original_id else None

        seen_ids = set()
        for item in extracted:
            if not isinstance(item, dict):
                continue
            link = item.get("link")
            sold_text = item.get("sold", "")

            if not link:
                continue
            full_link = "https:" + link if link.startswith("//") else link
            current_id = re.search(r'/products/.*-i(\d+)', full_link)
            if not current_id:
                continue
            pid = current_id.group(1)

            # 去重及排除原始商品
            if pid == original_id or pid in seen_ids:
                continue

            seen_ids.add(pid)

            # 解析销量文本，转换成数字
            match = re.search(r'([\d\.]+)([KMB]?)', sold_text.replace(",", ""))
            if match:
                num = float(match.group(1))
                suffix = match.group(2)
                if suffix == 'K':
                    num *= 1000
                elif suffix == 'M':
                    num *= 1_000_000
                sold_count = int(num)
            else:
                sold_count = 0

            competitor_data.append({
                "link": full_link,
                "sold_count": sold_count
            })

        # 输出所有商品链接和销量（未截断）
        print("\n所有抓取到的商品（未截断）：")
        for item in competitor_data:
            print(f"链接: {item['link']} | 销量: {item['sold_count']}")

        # 按销量降序排序
        competitor_data.sort(key=lambda x: x["sold_count"], reverse=True)

        # 输出前 max_products 个链接和销量
        print(f"\n按销量排序后前 {max_products} 个商品：")
        top_items = competitor_data[:max_products]
        for item in top_items:
            print(f"链接: {item['link']} | 销量: {item['sold_count']}")

        return [item["link"] for item in top_items]

    except Exception as e:
        print(f"crawl4ai 提取商品链接出错: {e}")
        return []


async def main():
    # 测试搜索功能
    test_url = "https://www.lazada.com.my/products/pdp-i3147797988-s15855846785.html"
    competitors = await search_competitors(test_url, platform="lazada", max_products=5)
    print("找到的竞品链接:")
    for comp in competitors:
        print(comp)

if __name__ == "__main__":
    asyncio.run(main())
