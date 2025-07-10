
import uuid
from agent.third_part.ffmpeg import merge_video_audio
from agent.ad_agent.utils import get_audio_duration
from agent.third_part.elevenlabs import text_to_speech_with_elevenlabs
from agent.utils import get_url_data
from agent.llm import simulate_image2videoInKeling
from agent.ad_agent.prompt import CREATE_AUDIO_TEXT_SYSTEM_PROMPT_en, CREATE_AUDIO_TEXT_HUMAN_PROMPT_en
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
from agent.llm import get_gemini_multimodal_model
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from agent.ad_agent.prompt import ANALYSE_IMAGE_SYSTEM_PROMPT_en, ANALYSE_IMAGE_RESPONSE_SCHEMA, ANALYSE_IMAGE_HUMAN_PROMPT_en
# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频
os.environ["LANGSMITH_API_KEY"] = "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"
os.environ["LANGSMITH_TRACING"] = "true"  # Enables LangSmith tracing
# Project name for organizing LangSmith traces
os.environ["LANGSMITH_PROJECT"] = "m2v_agent"

# 开头视频 or 中间视频


class VideoFragment(BaseModel):
    id: str = Field(default="", description="视频片段id")
    video_index: int = Field(description="视频索引")
    model_image: str = Field(default="", description="模特图片")
    model_image_info: str = Field(default="", description="模特图片信息")
    video_positive_prompt: str = Field(default="", description="视频正向prompt")
    video_negative_prompt: str = Field(default="", description="视频负向prompt")
    video_script: str = Field(default="", description="视频脚本(即音频文案)")
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    video_duration: int = Field(default=5, description="视频时长")
    audio_url: str = Field(default="", description="音频path(in local)")

# v1表示纯视频，v2表示视频+音频，v3表示视频+字幕+音频


class OutputVideo(BaseModel):
    video_url_v1: str = Field(default="", description="视频path(in local)")
    video_url_v2: str = Field(default="", description="视频path(in local)")
    video_url_v3: str = Field(default="", description="视频path(in local)")
    subtitle_text: dict = Field(default={}, description="字幕文案")
    audio_url: str = Field(default="", description="音频path(in local)")


class GenerateVideoState(BaseModel):
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    model_images: list = Field(description="模特图片（带商品）")
    video_fragment_duration: int = 5
    is_add_beginning: bool = False
    video_fragments: list[VideoFragment] = []
    output_video: OutputVideo = OutputVideo()


async def generate_video_fragments(state: GenerateVideoState, config):
    """
    初始化视频片段
    """
    for i, model_image in enumerate(state.model_images):
        video_fragment = VideoFragment(id=str(uuid.uuid4()), video_index=i+1,
                                       model_image=model_image, video_duration=state.video_fragment_duration)
        # 创建视频片段目录
        os.makedirs(os.path.join(
            config["configurable"]["temp_dir"], video_fragment.id), exist_ok=True)
        state.video_fragments.append(video_fragment)
    return {"video_fragments": state.video_fragments}


async def generate_video_script(state: GenerateVideoState, config):
    """
        使用gemini flash 对图片进行分析 + 商品信息  生成 展示商品的prompts (两步法)
    """
    # video_scripts = []
    # 对每个片段生成脚本

    for i, video_fragment in enumerate(state.video_fragments):
        model_image = video_fragment.model_image

        with open(model_image, "rb") as file:
            image_data = file.read()

        # 根据文件后缀获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(model_image)
        if mime_type is None:
            # 如果无法猜测，默认为 image/jpeg
            mime_type = "image/jpeg"

        gemini_generative_model = get_gemini_multimodal_model(
            system_prompt=ANALYSE_IMAGE_SYSTEM_PROMPT_en,
            response_schema=ANALYSE_IMAGE_RESPONSE_SCHEMA)

        response = gemini_generative_model.generate_content(
            [
                ANALYSE_IMAGE_HUMAN_PROMPT_en.format(product=state.product),
                Part.from_data(image_data, mime_type=mime_type)
            ]
        )
        content = response.candidates[0].content.parts[0].text
        content = json.loads(content)
        model_image_info = content["pictorial information"]
        video_fragment.model_image_info = model_image_info
        # video_script = chat_with_gemini_in_vertexai(CREATE_VIDEO_PROMPT_SYSTEM_PROMPT_en.format(duration=state.video_duration, video_content_limit=CREATE_VIDEO_PROMPT_LIMIT_ABOUT_MOVEMENT_en),
        #  CREATE_VIDEO_PROMPT_HUMAN_PROMPT_en.format( model_image_info=reconstruct_model_image_info(model_image_info), product=state.product, duration=state.video_duration))

    return {"video_fragments": state.video_fragments}


async def generate_video_prompt(state: GenerateVideoState, config):
    """
    生成视频prompt
    """

    for video_fragment in state.video_fragments:
        if video_fragment.video_index == 0:
            continue
        video_fragment.video_positive_prompt = "电商，模特，服装展示"
        video_fragment.video_negative_prompt = "旋转，低质量，抽象，扭曲，毁容，变形,deformation, a poor composition and deformed video, bad teeth, bad eyes, bad limbs"

    return {"video_fragments": state.video_fragments}


async def generate_video_with_prompt(state: GenerateVideoState, config):
    """
    根据脚本与图片生成视频
    """
    temp_dir = config.get("configurable").get("temp_dir")
    for video_fragment in state.video_fragments:
        image = video_fragment.model_image
        video_positive_prompt = video_fragment.video_positive_prompt
        video_negative_prompt = video_fragment.video_negative_prompt
        video_url = await simulate_image2videoInKeling(
            image, video_positive_prompt, video_negative_prompt, state.video_fragment_duration)
        # 下载视频
        if video_url:
            # 假如当前有文件则跳过
            local_video_path = os.path.join(
                temp_dir, video_fragment.id, "video_url_v1.mp4")
            # 直到video_number对应的文件不存在

            video_data = get_url_data(video_url)
            with open(local_video_path, "wb") as f:
                f.write(video_data)
            video_fragment.video_url_v1 = local_video_path
        else:
            logger.error("生成视频失败")
    return {"video_fragments": state.video_fragments}


async def generate_audio_text(state: GenerateVideoState, config):
    """
    根据商品信息，模特图片（图片信息），视频时长，语速(限制字数)，生成 字幕文案 + 音频，此处需要根据音频效果对文案进行不断调整
    """
    # 每个片段一段话（视频时长确定）

    # 假如添加开头数字人视频
    CREATE_AUDIO_TEXT_RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {},
        "required": []
    }
    fragment_info = ""
    for i, video_fragment in enumerate(state.video_fragments):
        fragment_info += f"( fragment{i}:{video_fragment.model_image_info})\n"
        CREATE_AUDIO_TEXT_RESPONSE_SCHEMA["properties"][f"fragment{i}"] = {
            "type": "string", "description": f"The video script for the {i}th segment"}
        CREATE_AUDIO_TEXT_RESPONSE_SCHEMA["required"].append(
            f"fragment{i}")
    gemini_generative_model = get_gemini_multimodal_model(
        system_prompt=CREATE_AUDIO_TEXT_SYSTEM_PROMPT_en,
        response_schema=CREATE_AUDIO_TEXT_RESPONSE_SCHEMA)

    response = gemini_generative_model.generate_content(
        [
            CREATE_AUDIO_TEXT_HUMAN_PROMPT_en.format(
                product=state.product, fragment_info=fragment_info),
        ]
    )
    content = json.loads(response.candidates[0].content.parts[0].text)
    state.output_video.subtitle_text = content
    for i, video_fragment in enumerate(state.video_fragments):
        video_fragment.video_script = content[f"fragment{i}"]
    return {"video_fragments": state.video_fragments, "output_video": state.output_video}


async def generate_audio(state: GenerateVideoState, config):
    """
    根据字幕文案，生成音频
    """
    temp_dir = config["configurable"]["temp_dir"]
    for i, video_fragment in enumerate(state.video_fragments):
        audio_file_path = os.path.join(
            temp_dir, video_fragment.id, "audio.mp3")
        video_url_v2 = os.path.join(
            temp_dir, video_fragment.id, "video_url_v2.mp4")
        audio_speed = 1.0

        text_to_speech_with_elevenlabs(
            conf.get("elevenlabs_api_key"), video_fragment.video_script, audio_file_path, "Laura", audio_speed)
        video_fragment.audio_url = audio_file_path
        # 音频时长必须小于视频时长，否则重新生成字幕文案
        audio_duration = get_audio_duration(audio_file_path)
        while audio_duration > video_fragment.video_duration:
            # 音频时长必须小于视频时长，否则重新生成字幕文案
            # 方法一：调口音速度
            # 方法二：调字幕 TODO 口音速度在0.7-1.2之间，1.2之后超过则需要重新生成字幕文案
            audio_speed += 0.05
            text_to_speech_with_elevenlabs(conf.get(
                "elevenlabs_api_key"), video_fragment.video_script, audio_file_path, "Laura", audio_speed)

        merge_video_audio(video_fragment.video_url_v1, audio_file_path,
                          video_url_v2, 1, None, None)
        video_fragment.video_url_v2 = video_url_v2
    return {"video_fragments": state.video_fragments}


async def evaluate_video_fragments(state: GenerateVideoState, config):
    """
    评估视频片段
    """
    # 1.评估点1：Motion Smoothness
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


def get_app():
    graph = StateGraph(GenerateVideoState)

    graph.add_node("generate_video_fragments",
                   generate_video_fragments)
    graph.add_node("generate_video_script",
                   generate_video_script)
    graph.add_node("generate_video_prompt",
                   generate_video_prompt)
    graph.add_node("generate_video_with_prompt",
                   generate_video_with_prompt)
    graph.add_node("generate_audio_text",
                   generate_audio_text)
    graph.add_node("generate_audio",
                   generate_audio)
    graph.add_node("evaluate_video_fragments",
                   evaluate_video_fragments)
    graph.add_node("video_stitching",
                   video_stitching)

    graph.add_edge(START, "generate_video_fragments")
    graph.add_edge("generate_video_fragments", "generate_video_script")
    graph.add_edge("generate_video_script", "generate_video_prompt")
    graph.add_edge("generate_video_prompt", "generate_video_with_prompt")
    graph.add_edge("generate_video_with_prompt", "generate_audio_text")
    graph.add_edge("generate_audio_text", "generate_audio")
    graph.add_edge("generate_audio", "evaluate_video_fragments")
    graph.add_edge("evaluate_video_fragments", "video_stitching")
    graph.add_edge("video_stitching", END)

    memory = MemorySaver()
    app = graph.compile(checkpointer=memory)
    return app


async def ainvoke_ad_agent_workflow(product: str, product_info: str, model_images: list, video_fragment_duration: int):
    with temp_dir() as temp_dir_path:
        app = get_app()
        configuration: RunnableConfig = {"configurable": {
            "thread_id": "1", "temp_dir": temp_dir_path}}
        result = await app.ainvoke({"product": product, "product_info": product_info, "model_images": model_images,  "video_fragment_duration": video_fragment_duration}, config=configuration)
        return result
