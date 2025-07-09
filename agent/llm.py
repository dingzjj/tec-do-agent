import uuid
from agent.third_part.aliyunoss import share_file_in_oss
import time
import asyncio
import httpx
from http import HTTPStatus
from dashscope import VideoSynthesis
from google import genai
from langchain_openai import AzureChatOpenAI
from google.oauth2 import service_account
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
import vertexai
from config import conf, logger
from openai import OpenAI
from langchain.prompts import SystemMessagePromptTemplate, ChatPromptTemplate


def create_azure_llm() -> AzureChatOpenAI:
    # 配置 Azure OpenAI 客户端
    return AzureChatOpenAI(
        api_key="0c7cf81130b7479f9391b327b2a1717f",  # API 密钥
        azure_endpoint="https://tecdoai-sweden-02.openai.azure.com",  # 替换为你的端点
        model="gpt-4o-mini",  # 选择模型
        deployment_name="tecdoai-sweden-02-gpt4o-mini",  # 替换为你的部署名称
        api_version="2024-08-01-preview",  # API 版本
    )


def chat_with_openai_in_azure(system_prompt: str, prompt: str) -> str:
    llm = create_azure_llm()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    response = llm.invoke(messages)
    return str(response.content)


def chat_once(llm, system_prompt: str, prompt: str) -> str:
    """
    单次对话
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    response = llm.invoke(messages)
    return str(response.content)


def chat_with_openai_in_azure_with_template(system_prompt_template: str, **kwargs) -> str:
    # 创建聊天提示模板
    chat_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt_template),
    ])

    llm = create_azure_llm()
    chain = chat_prompt | llm
    response = chain.invoke(kwargs)
    return str(response.content)


def chat_with_gemini_in_vertexai(system_prompt: str, prompt: str) -> str:
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get_file_path('gemini_conf'))
    vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)
    multimodal_model = GenerativeModel(
        model_name="gemini-2.5-flash-preview-04-17",
        system_instruction=system_prompt,
        generation_config=GenerationConfig(
            temperature=0.1)
    )

    # Query the model
    try:
        response = multimodal_model.generate_content(
            [
                prompt
            ]
        )
        return response.text
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return ""


def translate_with_gemini_in_vertexai(context: str) -> str:
    system_prompt = "你是一个专业的中文翻译员，请只提供翻译后的中文内容，避免添加任何其他解释或信息。"
    prompt = f"请将以下内容翻译成中文：{context}"
    try:
        gemini_result = chat_with_gemini_in_vertexai(system_prompt, prompt)
        return gemini_result
    except Exception as e:
        return context


def generate_embedding_with_openai(text: str) -> list[float]:
    query_vectors = [
        vec.embedding
        for vec in OpenAI(api_key=conf.get('openai_api_key'), base_url=conf.get('openai_api_base')).embeddings.create(input=text, model=config.get('openai_embedding_model')).data]
    return query_vectors[0]


def create_gemini_generative_model(system_prompt: str, response_schema: dict):
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get("gemini_conf"))
    vertexai.init(project='ca-biz-vypngh-y97n', credentials=credentials)

    # Load the model
    multimodal_model = GenerativeModel(
        model_name="gemini-2.5-flash-preview-04-17",
        system_instruction=system_prompt,
        generation_config=GenerationConfig(
            temperature=0.1, response_mime_type="application/json", response_schema=response_schema)
    )
    return multimodal_model


# Create Gemini create image model client
def create_gemini_create_image_model_client():
    credentials = service_account.Credentials.from_service_account_file(
        filename=conf.get("gemini_conf"),
        scopes=[conf.get("gemini_scopes")],
    )

    client = genai.Client(
        vertexai=True,
        project=conf.get("gemini_project"),
        location=conf.get("gemini_location"),
        credentials=credentials,
    )
    return client


# dashscope sdk >= 1.23.4

def i2v_with_tongyi(img_url, prompt, resolution, duration, prompt_extend=True):
    def get_video_url(img_url):
        if img_url.startswith("http"):
            return img_url
        else:
            return "file://" + img_url
    """
    通过通义的i2v模型生成视频
    img_url: 图片url
    prompt: 提示词
    resolution: 分辨率
    prompt_extend: 是否扩展提示词

    img_url:使用http:.... or 使用本地文件路径
    # 使用本地文件路径（file://+文件路径）
    # 使用绝对路径
    # img_url = "file://" + "/path/to/your/img.png"    # Linux/macOS
    # img_url = "file://" + "C:/path/to/your/img.png"  # Windows
    # 或使用相对路径
    # img_url = "file://" + "./img.png"                # 以实际路径为准

    return 返回的是远程url，需要下载
    """
    # call sync api, will return the result
    rsp = VideoSynthesis.call(api_key=conf.get("tongyi_api_key"),
                              model='wanx2.1-i2v-turbo',
                              prompt=prompt,
                              # negative_prompt='',  # 可选，负面提示词
                              # template='flying',# 模板，包括squish（解压捏捏）、flying（魔法悬浮）、carousel（时光木马）
                              img_url=get_video_url(img_url),
                              parameters={
                                  "resolution": resolution,
                                  "duration": duration,  # 视频时长wanx2.1-i2v-turbo：可选值为3、4或5;wanx2.1-i2v-plus：仅支持5秒
                                  "prompt_extend": prompt_extend
    }
    )
    if rsp.status_code == HTTPStatus.OK:
        result = rsp.output.video_url
        return result
    else:
        logger.error('Failed, status_code: %s, code: %s, message: %s' %
                     (rsp.status_code, rsp.code, rsp.message))


async def image2videoInKeling(img_path, positive_prompt, negative_prompt,  duration, model: str = "kling-v2-1-master"):
    # 使用keling的api生成视频，最终返回一个url，url是视频的地址

    http_client = httpx.Client(timeout=httpx.Timeout(
        600.0, connect=60.0), follow_redirects=True)
    KLING_API_KEY = conf.get("KLING_API_KEY")
    KLING_SECRET = conf.get("KLING_SECRET")
    KLING_API_BASE_URL = conf.get("KLING_API_BASE_URL")
#  TODO 将图片上传到图床(对象存储服务OSS)
    image_url = share_file_in_oss(img_path, f"{uuid.uuid4()}.jpg")
    payload = {
        # kling-v1, kling-v1-5, kling-v1-6, kling-v2-master, kling-v2-1, kling-v2-1-master
        "model_name": model,
        "mode": "pro",  # std 标准，pro 增强
        "image": image_url,
        "prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "duration": duration  # 枚举值：5，10
    }

    headers = {
        "X-API-Key": KLING_API_KEY,
        "X-Secret-Key": KLING_SECRET,
        "Content-Type": "application/json",
    }
    url = f"{KLING_API_BASE_URL}/gen_video_task_by_image_create"

    response = http_client.post(url, headers=headers, json=payload)

    task_id = response.json()["data"]["taskId"]

    headers = {
        "X-API-Key": KLING_API_KEY,
        "X-Secret-Key": KLING_SECRET,
        "Content-Type": "application/json",
    }
    url = f"{KLING_API_BASE_URL}/gen_video_task_by_image_get/{task_id}"
    interval = 30  # 每30秒检查一次任务状态
    start_time = time.time()
    max_wait = 600  # 最长等待时间10分钟

    while True:
        try:
            response = http_client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        except httpx.RequestError as e:
            logger.error(f"请求异常: {type(e).__name__}: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"请求失败，状态码：{e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"解析响应失败: {e}")
            return None
        task_status = data.get("task_status")
        if time.time() - start_time > max_wait:
            logger.error("等待超时，任务未完成。")
            return None

        if task_status == "processing":
            logger.info("视频正在处理中，继续等待...")
        elif task_status == "submitted":
            logger.info("任务已提交，等待处理...")
        elif task_status == "succeed":
            video_list = data.get("videos", [])
            if video_list:
                return video_list[0].get("url")
            else:
                logger.error("视频结果为空。")
                return None
        elif task_status == "failed":
            logger.error("任务失败，无法获取视频。")
            return None
        else:
            logger.error(f"未知任务状态: {task_status}")
        await asyncio.sleep(interval)
