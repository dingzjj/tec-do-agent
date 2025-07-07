from langchain_core.runnables import RunnableConfig
from config import conf
from config import logger
import requests
from agent.llm import i2v_with_tongyi
from agent.ad_agent.utils import reconstruct_model_image_info
from agent.llm import chat_with_gemini_in_vertexai
import json
import os
import mimetypes
from agent.llm import create_gemini_generative_model
from agent.ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from agent.ad_agent.prompt import CREATE_VIDEO_PROMPT_SYSTEM_PROMPT_en, CREATE_VIDEO_PROMPT_HUMAN_PROMPT_en


class GenerateVideoState(BaseModel):
    # 商品
    product: str = Field(default="")
    # 模特图片（带商品）
    model_images: list = []
    video_duration: int = 3
    # 视频脚本
    video_scripts: list = []


async def generate_video_script_with_image_and_product(state: GenerateVideoState):
    """
    使用gemini flash 对图片进行分析 + 商品信息  生成 展示商品的prompts (两步法)
    """
    with open(state.model_images[0], "rb") as file:
        image_data = file.read()

    # 根据文件后缀获取 MIME 类型
    mime_type, _ = mimetypes.guess_type(state.model_images[0])
    if mime_type is None:
        # 如果无法猜测，默认为 image/jpeg
        mime_type = "image/jpeg"

    gemini_generative_model = create_gemini_generative_model(
        system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
        response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

    response = gemini_generative_model.generate_content(
        [
            ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=state.product),
            Part.from_data(image_data, mime_type=mime_type)
        ]
    )

    # 生成展示商品的prompts
    content = response.candidates[0].content.parts[0].text
    model_image_info = json.loads(content)
    video_scripts = []
    video_scripts.append(chat_with_gemini_in_vertexai(CREATE_VIDEO_PROMPT_SYSTEM_PROMPT_en.format(duration=state.video_duration), CREATE_VIDEO_PROMPT_HUMAN_PROMPT_en.format(
        model_image_info=reconstruct_model_image_info(model_image_info), product=state.product, duration=state.video_duration)))
    return {"video_scripts": video_scripts}


async def generate_video_with_script(state: GenerateVideoState):
    """
    根据脚本与图片生成视频
    """
    image = state.model_images[0]
    video_script = state.video_scripts[0]
    video_url = i2v_with_tongyi(
        image, video_script, "480p", state.video_duration, True)
    # 下载视频
    if video_url:
        video_data = requests.get(video_url).content
        with open(os.path.join(conf.get_path("temp_dir"), "video.mp4"), "wb") as f:
            f.write(video_data)
    else:
        logger.error("生成视频失败")
    return {"video_url": video_url}


def get_app():
    graph = StateGraph(GenerateVideoState)
    graph.add_node("generate_video_script_with_image_and_product",
                   generate_video_script_with_image_and_product)
    graph.add_node("generate_video_with_script", generate_video_with_script)
    graph.add_edge(START, "generate_video_script_with_image_and_product")
    graph.add_edge("generate_video_script_with_image_and_product",
                   "generate_video_with_script")
    graph.add_edge("generate_video_with_script", END)
    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_ad_agent_workflow(product: str, model_images: list, video_duration: int):
    app = get_app()
    configuration: RunnableConfig = {"configurable": {"thread_id": "1"}}
    result = await app.ainvoke({"product": product, "model_images": model_images, "video_duration": video_duration}, config=configuration)
    return result
