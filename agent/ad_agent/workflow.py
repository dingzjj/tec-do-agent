from agent.llm import image2videoInKeling
from agent.ad_agent.utils import concatenate_videos_from_urls
from agent.utils import temp_dir
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
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig

# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频


class VideoFragment(BaseModel):
    model_image: str = Field(default="", description="模特图片")
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    video_duration: int = Field(default=5, description="视频时长")
    video_script: str = Field(default="", description="视频脚本")

# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频


class OutputVideo(BaseModel):
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    subtitle_text: str = Field(default="", description="字幕文案")
    audio_url: str = Field(default="", description="音频path(in local)")


class GenerateVideoState(BaseModel):
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    model_images: list = Field(description="模特图片（带商品）")
    video_fragment_duration: int = 5
    video_fragments: list[VideoFragment] = []
    output_video: OutputVideo = OutputVideo()


async def generate_video_fragments(state: GenerateVideoState, config):
    """
    初始化视频片段
    """
    for i in range(len(state.model_images)):
        model_image = state.model_images[i]
        video_fragment = VideoFragment(
            model_image=model_image, video_duration=state.video_fragment_duration)
        state.video_fragments.append(video_fragment)
    return {"video_fragments": state.video_fragments}


async def generate_video_script(state: GenerateVideoState, config):
    """
        使用gemini flash 对图片进行分析 + 商品信息  生成 展示商品的prompts (两步法)
    """
    video_scripts = []
    # 对每个片段生成脚本

    # for i in range(len(state.model_images)):
    #     model_image = state.model_images[i]
    #     with open(model_image, "rb") as file:
    #         image_data = file.read()

    #     # 根据文件后缀获取 MIME 类型
    #     mime_type, _ = mimetypes.guess_type(model_image)
    #     if mime_type is None:
    #         # 如果无法猜测，默认为 image/jpeg
    #         mime_type = "image/jpeg"

    #     gemini_generative_model = create_gemini_generative_model(
    #         system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
    #         response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

    #     response = gemini_generative_model.generate_content(
    #         [
    #             ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=state.product),
    #             Part.from_data(image_data, mime_type=mime_type)
    #         ]
    #     )
    #     # 提示词：电商，模特，服装展示

    #     # 生成展示商品的prompts
    #     content = response.candidates[0].content.parts[0].text
    #     model_image_info = json.loads(content)
    #     video_script = "电商，模特，服装展示"
    #     # video_script = chat_with_gemini_in_vertexai(CREATE_VIDEO_PROMPT_SYSTEM_PROMPT_en.format(duration=state.video_duration, video_content_limit=CREATE_VIDEO_PROMPT_LIMIT_ABOUT_MOVEMENT_en),
    #     #  CREATE_VIDEO_PROMPT_HUMAN_PROMPT_en.format( model_image_info=reconstruct_model_image_info(model_image_info), product=state.product, duration=state.video_duration))
    #     video_scripts.append(video_script)

    return {"video_fragments": state.video_fragments}


async def generate_video_prompt(state: GenerateVideoState, config):
    """
    生成视频prompt
    """

    for video_fragment in state.video_fragments:
        video_fragment.video_positive_prompt = "电商，模特，服装展示"
        video_fragment.video_negative_prompt = "旋转，低质量，抽象，扭曲，毁容，变形,deformation, a poor composition and deformed video, bad teeth, bad eyes, bad limbs"

    return {"video_fragments": state.video_fragments}


async def generate_video_with_prompt(state: GenerateVideoState, config):
    """
    根据脚本与图片生成视频
    """
    temp_dir = config.get("configurable").get("temp_dir")
    video_number = 1
    video_fragments = []
    for video_fragment in state.video_fragments:
        image = video_fragment.model_image
        video_positive_prompt = video_fragment.video_positive_prompt
        video_negative_prompt = video_fragment.video_negative_prompt
        video_url = await image2videoInKeling(
            image, video_positive_prompt, video_negative_prompt, state.video_fragment_duration)
        # 下载视频

        if video_url:
            # 假如当前有文件则跳过
            local_video_path = os.path.join(
                temp_dir, f"video_{video_number}.mp4")
            # 直到video_number对应的文件不存在
            while os.path.exists(local_video_path):
                video_number += 1
                local_video_path = os.path.join(
                    temp_dir, f"video_{video_number}.mp4")

            video_data = requests.get(video_url).content
            with open(local_video_path, "wb") as f:
                f.write(video_data)
            video_fragment.video_url_v1 = local_video_path
            video_number += 1
        else:
            logger.error("生成视频失败")
    return {"video_fragments": video_fragments}


async def evaluate_video_fragments(state: GenerateVideoState, config):
    """
    评估视频片段
    """
    pass


async def video_stitching(state: GenerateVideoState, config):
    """
    视频拼接
    """
    temp_dir = config.get("configurable").get("temp_dir")

    video_list = []
    for video_fragment in state.video_fragments:
        video_list.append(video_fragment.video_url_v1)
    output_path = os.path.join(temp_dir, "merged_output.mp4")

    state.output_video.video_url_v1 = concatenate_videos_from_urls(
        video_list, output_path=output_path)
    return {"output_video": state.output_video}


async def generate_audio_text_and_audio(state: GenerateVideoState, config):
    """
    根据商品信息，模特图片（图片信息），视频时长，语速(限制字数)，生成 字幕文案 + 音频，此处需要根据音频效果对文案进行不断调整
    """
    # 每个片段一段话（视频时长确定）

    pass


async def add_subtitles(state: GenerateVideoState, config):
    """
    添加字幕(文案)
    """
    # 先根据商品信息，视频时长，生成文案

    pass


def get_app():
    graph = StateGraph(GenerateVideoState)

    graph.add_node("generate_video_fragments",
                   generate_video_fragments)
    graph.add_node("generate_video_prompt",
                   generate_video_prompt)
    graph.add_node("generate_video_with_prompt",
                   generate_video_with_prompt)
    graph.add_node("evaluate_video_fragments",
                   evaluate_video_fragments)
    graph.add_node("video_stitching",
                   video_stitching)
    graph.add_node("add_subtitles",
                   add_subtitles)

    graph.add_edge(START, "generate_video_fragments")
    graph.add_edge("generate_video_fragments",
                   "generate_video_prompt")
    graph.add_edge("generate_video_prompt",
                   "generate_video_with_prompt")
    graph.add_edge("generate_video_with_prompt",
                   "evaluate_video_fragments")
    graph.add_edge("evaluate_video_fragments",
                   "video_stitching")
    graph.add_edge("video_stitching",
                   "add_subtitles")
    graph.add_edge("add_subtitles", END)

    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_ad_agent_workflow(product: str, model_images: list, video_fragment_duration: int):
    with temp_dir() as temp_dir_path:
        app = get_app()
        configuration: RunnableConfig = {"configurable": {
            "thread_id": "1", "temp_dir": temp_dir_path}}
        result = await app.ainvoke({"product": product, "model_images": model_images, "video_fragment_duration": video_fragment_duration}, config=configuration)
        return result
