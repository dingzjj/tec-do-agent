from agent.utils import judge_file_exist
from agent.utils import temp_dir
from config import logger
from moviepy.editor import VideoFileClip, concatenate_videoclips
import os
import requests
from agent.ad_agent.prompt import ANALYSE_IMAGE_RESPONSE_SCHEMA


def reconstruct_model_image_info(model_image_info: dict) -> str:
    return f"""{ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["connection"]["description"]}:{model_image_info["connection"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["composition"]["description"]}:{model_image_info["composition"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["Character posture"]["description"]}:{model_image_info["Character posture"]}
    """


def download_video(url, filename):
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    else:
        logger.error(f"下载失败: {url}")
        return None
    return filename


def concatenate_videos_from_urls(video_urls, output_path="output.mp4"):
    if len(video_urls) == 0:
        raise Exception("视频列表为空")
    clips = []
    with temp_dir() as temp_dir_path:
        for i, url in enumerate(video_urls):
            # 判断是否是本地文件，是本地文件的话，判断文件是否存在，如果是url则下载到本地的临时目录中
            downloaded = judge_file_exist(
                url, temp_dir_path, f"temp_video_{i}.mp4")
            if downloaded["exist"]:
                logger.info(f"merge video: {downloaded['path']}")
                clip = VideoFileClip(downloaded["path"])
                clips.append(clip)
            else:
                if downloaded["type"] == "url":
                    logger.error(f"下载失败: {url}")
                else:
                    logger.error(f"文件不存在: {url}")
        if len(clips) == 0:
            logger.error("未找到可用的视频文件。")
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(
            output_path, codec="libx264", audio_codec="aac")
        return output_path
