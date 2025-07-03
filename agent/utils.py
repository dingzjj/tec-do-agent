from crawl4ai import BrowserConfig

from crawl4ai.extraction_strategy import JsonCssExtractionStrategy
from crawl4ai import CrawlerRunConfig
from crawl4ai import AsyncWebCrawler


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
        wait_for=".pdp-mod-spec-item-text",
        # cache_mode=CacheMode.BYPASS,
        verbose=True,
        extraction_strategy=css_strategy,

    )
    crawler = AsyncWebCrawler(config=browser_config)
    result = await crawler.arun(url=url, config=crawler_run_config)
    return result.extracted_content
