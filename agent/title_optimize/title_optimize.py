from langgraph.graph import StateGraph, START, END
from config import logger
from pydantic import BaseModel


class TitleOptimizeState(BaseModel):
    url: str


async def crawl_product_info(state: TitleOptimizeState):

    return state

graph = StateGraph(TitleOptimizeState)
graph.add_node("crawl_product_info", crawl_product_info)
graph.add_edge(START, "crawl_product_info")
graph.add_edge("crawl_product_info", END)

app = graph.compile()
