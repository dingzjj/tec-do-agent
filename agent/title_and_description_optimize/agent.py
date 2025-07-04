from langgraph.prebuilt import create_react_agent
from agent.llm import create_azure_llm
from agent.prompt import GET_KEYWORDS_AGENT_PROMPT_TEMPLATE
from pydantic import BaseModel

# 采用reAct

from agent.tools import judge_if_brand, tavily_search


class GetKeywordsAgent():
    class Keywords(BaseModel):
        keywords: list[str]

    def __init__(self) -> None:
        self.llm = create_azure_llm()
        self.tool_list = [judge_if_brand, tavily_search]

    async def invoke(self, product_title: str, product_description: str) -> list[str]:
        prompt_template = GET_KEYWORDS_AGENT_PROMPT_TEMPLATE
        prompt = prompt_template.format(
            product_title=product_title, product_description=product_description)
        agent = create_react_agent(model=self.llm, tools=self.tool_list,
                                   prompt=prompt, response_format=self.Keywords)
        keywords = await agent.ainvoke({"product_title": product_title,
                                        "product_description": product_description})

        print(keywords)
        return keywords["keywords"]
