from agent.title_and_description_optimize.pojo import ProductInfo
from langgraph.prebuilt import create_react_agent
from agent.llm import create_azure_llm
from agent.prompt import GET_KEYWORDS_AGENT_PROMPT_TEMPLATE, CREATE_TITLE_AGENT_PROMPT_TEMPLATE
from agent.title_and_description_optimize.pojo import Keywords
# 采用reAct

from agent.tools import judge_if_brand, product_tavily_search


class GetKeywordsAgent():

    def __init__(self) -> None:
        self.llm = create_azure_llm()
        self.tool_list = [judge_if_brand, product_tavily_search]

    async def invoke(self, product_title: str, product_description: str, product_category: str) -> Keywords:
        prompt_template = GET_KEYWORDS_AGENT_PROMPT_TEMPLATE
        prompt = prompt_template.format(
            product_title=product_title, product_description=product_description, product_category=product_category)
        agent = create_react_agent(model=self.llm, tools=self.tool_list,
                                   prompt=prompt, response_format=Keywords)
        agent_result = await agent.ainvoke({})
        keywords: Keywords = agent_result["structured_response"]
        return keywords


class CreateTitleAgent():
    def __init__(self) -> None:
        self.llm = create_azure_llm()
        self.tool_list = [judge_if_brand, product_tavily_search]

    async def invoke(self, product_title: str, product_description: str, suggest: str, keywords: Keywords) -> ProductInfo:
        prompt_template = CREATE_TITLE_AGENT_PROMPT_TEMPLATE
        prompt = prompt_template.format(
            product_title=product_title, product_description=product_description, suggest=suggest, keywords=str(keywords))
        agent = create_react_agent(model=self.llm, tools=self.tool_list,
                                   prompt=prompt, response_format=ProductInfo)
        agent_result = await agent.ainvoke({})
        product_info: ProductInfo = agent_result["structured_response"]
        return product_info
