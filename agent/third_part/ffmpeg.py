import ffmpeg
from typing import Optional


def merge_video_audio(
    video_file: str,
    audio_file: str,
    output_file: str,
    volume: float,
    audio_start: Optional[str] = None,  # 音频起始时间，格式如 "00:00:03.500"
    audio_duration: Optional[str] = None,  # 音频持续时间，格式如 "00:00:10.500"
    use_shortest: bool = False,
    audio_delay: float = 0,
):
    """
    将视频与音频合并，支持设置音量、控制输出长度、音频延迟、音频起始时间和持续时间。

    参数:
        video_file (str): 视频文件路径。
        audio_file (str): 音频文件路径。
        output_file (str): 输出视频文件路径。
        volume (float or None): 音量倍数，例如 3 表示提高 300% 音量。
        use_shortest (bool): 如果为 True，则输出以最短输入流为准。
        audio_delay (float): 音频延迟时间（秒），最多3位小数。
        audio_start (str): 音频起始时间，格式如 "00:00:03.500"，默认为None。
        audio_duration (str): 音频持续时间，格式如 "00:00:10.500"，默认为None。
    """
    # 输入流
    video_input = ffmpeg.input(video_file)

    # 构建音频输入，添加 -ss 和 -t 参数
    audio_input_args = {}
    if audio_start:
        audio_input_args["ss"] = audio_start
    if audio_duration:
        audio_input_args["t"] = audio_duration

    audio_input = ffmpeg.input(audio_file, **audio_input_args)

    # 视频流直接复制
    video = video_input.video

    # 音频流处理
    audio = audio_input.audio

    # 应用音频延迟（限制为3位小数）
    if audio_delay > 0:
        delay_seconds = round(audio_delay, 3)
        delay_ms = int(delay_seconds * 1000)  # 转换为整数毫秒
        audio = audio.filter_(
            "adelay", f"{delay_ms}|{delay_ms}"
        )  # 对立体声的两个通道都延迟

    # 音量调整
    if volume is not None:
        audio = audio.filter_("volume", volume)

    # 构建输出命令
    output_args = {"vcodec": "copy", "acodec": "aac", "strict": "experimental"}

    # 添加 shortest 参数（如果需要）
    if use_shortest:
        output_args["shortest"] = None

    # 创建输出对象
    output = ffmpeg.output(video, audio, output_file, **output_args)

    # 执行命令
    try:
        output.run(overwrite_output=True)
        print(f"✅ 成功生成合并后的视频：{output_file}")
    except ffmpeg.Error as e:
        print("❌ FFmpeg 错误:")
        print("stdout:", e.stdout.decode() if e.stdout else None)
        print("stderr:", e.stderr.decode() if e.stderr else None)
        raise
