# -*- coding:utf-8 -*-

from agent.agent import SEOAgent
import csv
import datetime
import getpass
import hashlib
import html
import json
import os
import pickle
import re
import threading
from enum import Enum
from typing import List, Union
from typing import TYPE_CHECKING

import colorama
import gradio as gr
import pandas as pd
import requests
import tiktoken
from config import logger
from markdown import markdown
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pypinyin import lazy_pinyin
from agent.llm import chat_with_openai_in_azure
from src.config import retrieve_proxy, hide_history_when_not_logged_in, config_file
from src.presets import ALREADY_CONVERTED_MARK, HISTORY_DIR, TEMPLATES_DIR, i18n, LOCAL_MODELS, ONLINE_MODELS
from src.shared import state

if TYPE_CHECKING:
    from typing import TypedDict

    class DataframeData(TypedDict):
        headers: List[str]
        data: List[List[Union[str, int, bool]]]


def html_to_text(html_content: str) -> str:
    """
    将HTML格式的聊天消息转换为纯文本

    Args:
        html_content: HTML格式的消息内容

    Returns:
        转换后的纯文本内容
    """
    if not html_content:
        return ""

    # 从后往前匹配，找到最后一个div标签内的内容
    div_matches = list(re.finditer(
        r'<div[^>]*>(.*?)</div>', html_content, re.DOTALL))
    if div_matches:
        # 取最后一个匹配的div内容
        text = div_matches[-1].group(1)
    else:
        # 如果没有找到div标签，则移除所有HTML标签
        text = re.sub(r'<[^>]+>', '', html_content)

    # 解码HTML实体
    text = html.unescape(text)

    # 清理多余的空白字符
    text = re.sub(r'\s+', ' ', text)

    # 移除首尾空白
    text = text.strip()

    return text


def extract_chat_history(chatbot) -> List[List[str]]:
    """
    从chatbot中提取纯文本对话历史

    Args:
        chatbot: 包含HTML格式对话的列表

    Returns:
        包含纯文本对话的列表，每个元素为[用户消息, 机器人回复]
    """
    if not chatbot:
        return []

    chat_history = []
    for message_pair in chatbot:
        if len(message_pair) >= 2:
            user_message = html_to_text(message_pair[0])
            bot_message = html_to_text(message_pair[1])
            chat_history.append([user_message, bot_message])

    return chat_history


def predict(user_question: str, chatbot, use_streaming_checkbox, language_select_dropdown):
    print(f"user_question: {user_question}")
    print(f"chatbot: {chatbot}")
    # TODO 提取chatbot中的对话内容
    # 提取纯文本对话历史
    chat_history = extract_chat_history(chatbot)
    # TODO 使用agent来进行回复

    # 调用agent
    agent = SEOAgent()
    agent.predict(user_question, chat_history)
    # chatbot += [(user_question, chat_with_openai_in_azure(
    #     system_prompt=f"用{language_select_dropdown}回答用户的问题", prompt=user_question))]
    return chatbot


def billing_info(current_model):
    if current_model:
        return current_model.billing_info()


def set_key(current_model, *args):
    return current_model.set_key(*args)


def load_chat_history(current_model, *args):
    return current_model.load_chat_history(*args)


def delete_chat_history(current_model, *args):
    return current_model.delete_chat_history(*args)


def interrupt(current_model, *args):
    return current_model.interrupt(*args)


def retry(current_model, *args):
    iter = current_model.retry(*args)
    for i in iter:
        yield i


def delete_first_conversation(current_model, *args):
    return current_model.delete_first_conversation(*args)


def delete_last_conversation(current_model, *args):
    return current_model.delete_last_conversation(*args)


def set_system_prompt(current_model, *args):
    return current_model.set_system_prompt(*args)


def rename_chat_history(current_model, *args):
    return current_model.rename_chat_history(*args)


def auto_name_chat_history(current_help_model, *args):
    # TODO 输出是historySelectList
    # 只有第一次才需要对对话进行命名
    if current_help_model:
        return current_help_model.auto_name_chat_history(*args)
    else:
        logger.error("current_help_model is None")


def export_markdown(current_model, *args):
    return current_model.export_markdown(*args)


def upload_chat_history(current_model, *args):
    return current_model.load_chat_history(*args)


def set_token_upper_limit(current_model, *args):
    return current_model.set_token_upper_limit(*args)


def set_temperature(current_model, *args):
    current_model.set_temperature(*args)


def set_top_p(current_model, *args):
    current_model.set_top_p(*args)


def set_n_choices(current_model, *args):
    current_model.set_n_choices(*args)


def set_stop_sequence(current_model, *args):
    current_model.set_stop_sequence(*args)


def set_max_tokens(current_model, *args):
    current_model.set_max_tokens(*args)


def set_presence_penalty(current_model, *args):
    current_model.set_presence_penalty(*args)


def set_frequency_penalty(current_model, *args):
    current_model.set_frequency_penalty(*args)


def set_logit_bias(current_model, *args):
    current_model.set_logit_bias(*args)


def set_user_identifier(current_model, *args):
    current_model.set_user_identifier(*args)


def set_single_turn(current_model, *args):
    current_model.set_single_turn(*args)


def handle_file_upload(current_model, *args):
    return current_model.handle_file_upload(*args)


def handle_summarize_index(current_model, *args):
    return current_model.summarize_index(*args)


def like(current_model, *args):
    return current_model.like(*args)


def dislike(current_model, *args):
    return current_model.dislike(*args)


def count_token(input_str):
    encoding = tiktoken.get_encoding("cl100k_base")
    if type(input_str) == dict:
        input_str = f"role: {input_str['role']
                             }, content: {input_str['content']}"
    length = len(encoding.encode(input_str))
    return length


def markdown_to_html_with_syntax_highlight(md_str):  # deprecated
    def replacer(match):
        lang = match.group(1) or "text"
        code = match.group(2)

        try:
            lexer = get_lexer_by_name(lang, stripall=True)
        except ValueError:
            lexer = get_lexer_by_name("text", stripall=True)

        formatter = HtmlFormatter()
        highlighted_code = highlight(code, lexer, formatter)

        return f'<pre><code class="{lang}">{highlighted_code}</code></pre>'

    code_block_pattern = r"```(\w+)?\n([\s\S]+?)\n```"
    md_str = re.sub(code_block_pattern, replacer, md_str, flags=re.MULTILINE)

    html_str = markdown(md_str)
    return html_str


def normalize_markdown(md_text: str) -> str:  # deprecated
    lines = md_text.split("\n")
    normalized_lines = []
    inside_list = False

    for i, line in enumerate(lines):
        if re.match(r"^(\d+\.|-|\*|\+)\s", line.strip()):
            if not inside_list and i > 0 and lines[i - 1].strip() != "":
                normalized_lines.append("")
            inside_list = True
            normalized_lines.append(line)
        elif inside_list and line.strip() == "":
            if i < len(lines) - 1 and not re.match(
                    r"^(\d+\.|-|\*|\+)\s", lines[i + 1].strip()
            ):
                normalized_lines.append(line)
            continue
        else:
            inside_list = False
            normalized_lines.append(line)

    return "\n".join(normalized_lines)


def convert_mdtext(md_text):  # deprecated
    code_block_pattern = re.compile(r"```(.*?)(?:```|$)", re.DOTALL)
    inline_code_pattern = re.compile(r"`(.*?)`", re.DOTALL)
    code_blocks = code_block_pattern.findall(md_text)
    non_code_parts = code_block_pattern.split(md_text)[::2]

    result = []
    raw = f'<div class="raw-message hideM">{html.escape(md_text)}</div>'
    for non_code, code in zip(non_code_parts, code_blocks + [""]):
        if non_code.strip():
            non_code = normalize_markdown(non_code)
            result.append(markdown(non_code, extensions=["tables"]))
        if code.strip():
            # _, code = detect_language(code)  # 暂时去除代码高亮功能，因为在大段代码的情况下会出现问题
            # code = code.replace("\n\n", "\n") # 暂时去除代码中的空行，因为在大段代码的情况下会出现问题
            code = f"\n```{code}\n\n```"
            code = markdown_to_html_with_syntax_highlight(code)
            result.append(code)
    result = "".join(result)
    output = f'<div class="md-message">{result}</div>'
    output += raw
    output += ALREADY_CONVERTED_MARK
    return output


def clip_rawtext(chat_message, need_escape=True):
    # first, clip hr line
    hr_pattern = r'\n\n<hr class="append-display no-in-raw" />(.*?)'
    hr_match = re.search(hr_pattern, chat_message, re.DOTALL)
    message_clipped = chat_message[: hr_match.start(
    )] if hr_match else chat_message
    # second, avoid agent-prefix being escaped
    agent_prefix_pattern = (
        r'(<!-- S O PREFIX -->.*?<!-- E O PREFIX -->)'
    )
    # agent_matches = re.findall(agent_prefix_pattern, message_clipped)
    agent_parts = re.split(agent_prefix_pattern,
                           message_clipped, flags=re.DOTALL)
    final_message = ""
    for i, part in enumerate(agent_parts):
        if i % 2 == 0:
            if part != "" and part != "\n":
                final_message += (
                    f'<pre class="fake-pre">{escape_markdown(part)}</pre>'
                    if need_escape
                    else f'<pre class="fake-pre">{part}</pre>'
                )
        else:
            part = part.replace(' data-fancybox="gallery"', '')
            final_message += part
    return final_message


def convert_bot_before_marked(chat_message):
    """
    注意不能给输出加缩进, 否则会被marked解析成代码块
    """
    if '<div class="md-message">' in chat_message:
        return chat_message
    else:
        raw = f'<div class="raw-message hideM">{
            clip_rawtext(chat_message)}</div>'
        # really_raw = f'{START_OF_OUTPUT_MARK}<div class="really-raw hideM">{clip_rawtext(chat_message, need_escape=False)}\n</div>{END_OF_OUTPUT_MARK}'

        code_block_pattern = re.compile(r"```(.*?)(?:```|$)", re.DOTALL)
        code_blocks = code_block_pattern.findall(chat_message)
        non_code_parts = code_block_pattern.split(chat_message)[::2]
        result = []
        for non_code, code in zip(non_code_parts, code_blocks + [""]):
            if non_code.strip():
                result.append(non_code)
            if code.strip():
                code = f"\n```{code}\n```"
                result.append(code)
        result = "".join(result)
        md = f'<div class="md-message">\n\n{result}\n</div>'
        return raw + md


def convert_user_before_marked(chat_message):
    if '<div class="user-message">' in chat_message:
        return chat_message
    else:
        return f'<div class="user-message">{escape_markdown(chat_message)}</div>'


def escape_markdown(text):
    """
    Escape Markdown special characters to HTML-safe equivalents.
    """
    escape_chars = {
        # ' ': '&nbsp;',
        "_": "&#95;",
        "*": "&#42;",
        "[": "&#91;",
        "]": "&#93;",
        "(": "&#40;",
        ")": "&#41;",
        "{": "&#123;",
        "}": "&#125;",
        "#": "&#35;",
        "+": "&#43;",
        "-": "&#45;",
        ".": "&#46;",
        "!": "&#33;",
        "`": "&#96;",
        ">": "&#62;",
        "<": "&#60;",
        "|": "&#124;",
        "$": "&#36;",
        ":": "&#58;",
        "\n": "<br>",
    }
    text = text.replace("    ", "&nbsp;&nbsp;&nbsp;&nbsp;")
    return "".join(escape_chars.get(c, c) or c for c in text)


def convert_asis(userinput):  # deprecated
    return (
        f'<p style="white-space:pre-wrap;">{html.escape(userinput)}</p>'
        + ALREADY_CONVERTED_MARK
    )


def detect_converted_mark(userinput):  # deprecated
    try:
        if userinput.endswith(ALREADY_CONVERTED_MARK):
            return True
        else:
            return False
    except:
        return True


def detect_language(code):  # deprecated
    if code.startswith("\n"):
        first_line = ""
    else:
        first_line = code.strip().split("\n", 1)[0]
    language = first_line.lower() if first_line else ""
    code_without_language = code[len(
        first_line):].lstrip() if first_line else code
    return language, code_without_language


def construct_text(role, text):
    return {"role": role, "content": text}


def construct_user(text):
    return construct_text("user", text)


def construct_system(text):
    return construct_text("system", text)


def construct_assistant(text):
    return construct_text("assistant", text)

# 保存聊天记录


def auto_increase_filename(dir_path):
    """
    获取dir_path下最大的history id 并且+1，假如创建文件时报错，则+1重试直到创建成功

    Args:
        dir_path: 目录路径

    Returns:
        str: 生成的文件名（不包含扩展名）
    """
    # 确保目录存在
    os.makedirs(dir_path, exist_ok=True)

    # 获取目录下所有.json文件
    history_files = get_file_names_by_type(dir_path, [".json"])

    # 提取文件名（不含扩展名）
    history_names = [f[:f.rfind(".")]
                     for f in history_files if f.endswith(".json")]

    # 查找最大的数字ID
    max_id = 0
    for name in history_names:
        # 尝试从文件名中提取数字ID
        # 支持多种格式：纯数字、带前缀的数字等
        import re
        number_match = re.search(r'(\d+)', name)
        if number_match:
            try:
                current_id = int(number_match.group(1))
                max_id = max(max_id, current_id)
            except ValueError:
                continue

    # 从最大ID+1开始尝试
    current_id = max_id + 1

    # 尝试创建文件名，如果冲突则递增
    while True:
        # 生成新的文件名
        new_filename = f"{current_id}"

        # 检查文件是否已存在
        file_path = os.path.join(dir_path, f"{new_filename}.json")

        if not os.path.exists(file_path):
            # 尝试创建文件来验证是否可用
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('')  # 创建空文件
                # 如果成功创建，删除测试文件并返回文件名
                return file_path
            except (OSError, IOError) as e:
                logger.warning(f"无法创建文件 {file_path}: {e}")
                # 如果创建失败，继续尝试下一个ID
                current_id += 1
                continue
        else:
            # 文件已存在，尝试下一个ID
            current_id += 1

# 保存文件


def save_chat_history_util(chatbot, user_name, filename, dialogue_title):
    # filename必须要以json结尾，不是则换为json
    if not filename.endswith(".json"):
        filename += ".json"
    history_file_path = os.path.join(HISTORY_DIR, user_name, filename)

    # 如果文件存在也能覆盖写入
    json_data = {
        "dialogue_title": dialogue_title,
        "history": get_history_from_chatbot(chatbot),
    }
    with open(history_file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=4)
    return history_file_path


def sorted_by_pinyin(list):
    return sorted(list, key=lambda char: lazy_pinyin(char)[0][0])


def sorted_by_last_modified_time(list, dir):
    return sorted(
        list, key=lambda char: os.path.getctime(os.path.join(dir, char)), reverse=True
    )


def get_file_names_by_type(dir, filetypes=[".json"]):
    os.makedirs(dir, exist_ok=True)
    files = []
    for type in filetypes:
        files += [f for f in os.listdir(dir) if f.endswith(type)]
    return files


def get_file_names_by_pinyin(dir, filetypes=[".json"]):
    files = get_file_names_by_type(dir, filetypes)
    if files != [""]:
        files = sorted_by_pinyin(files)
    logger.debug(f"files are:{files}")
    return files


def get_file_names_dropdown_by_pinyin(dir, filetypes=[".json"]):
    files = get_file_names_by_pinyin(dir, filetypes)
    return gr.Dropdown.update(choices=files)


def get_file_names_by_last_modified_time(dir, filetypes=[".json"]):
    files = get_file_names_by_type(dir, filetypes)
    if files != [""]:
        files = sorted_by_last_modified_time(files, dir)
    logger.debug(f"files are:{files}")
    return files


def get_history_names(user_name=""):
    logger.debug(f"从用户 {user_name} 中获取历史记录文件名列表")
    if user_name == "" and hide_history_when_not_logged_in:
        return []
    else:
        history_files = get_file_names_by_last_modified_time(
            os.path.join(HISTORY_DIR, user_name)
        )
        history_files = [f[: f.rfind(".")] for f in history_files]
        return history_files


def get_first_history_name(user_name=""):
    history_names = get_history_names(user_name)
    return history_names[0] if history_names else ""


def get_history_list(user_name=""):
    history_names = get_history_names(user_name)
    return gr.Radio.update(choices=history_names)


def init_history_list(user_name="", prepend=""):
    # TODO 改善
    history_names = get_history_names(user_name)
    if prepend and prepend not in history_names:
        history_names.insert(0, prepend)
    return gr.Radio.update(
        choices=history_names, value=history_names[0] if history_names else ""
    )


def filter_history(user_name, keyword):
    history_names = get_history_names(user_name)
    try:
        history_names = [
            name for name in history_names if re.search(keyword, name)]
        return gr.update(choices=history_names)
    except:
        return gr.update(choices=history_names)


def load_template(filename, mode=0):
    logger.debug(f"加载模板文件{filename}，模式为{mode}（0为返回字典和下拉菜单，1为返回下拉菜单，2为返回字典）")
    lines = []
    if filename.endswith(".json"):
        with open(os.path.join(TEMPLATES_DIR, filename), "r", encoding="utf8") as f:
            lines = json.load(f)
        lines = [[i["act"], i["prompt"]] for i in lines]
    else:
        with open(
                os.path.join(TEMPLATES_DIR, filename), "r", encoding="utf8"
        ) as csvfile:
            reader = csv.reader(csvfile)
            lines = list(reader)
        lines = lines[1:]
    if mode == 1:
        return sorted_by_pinyin([row[0] for row in lines])
    elif mode == 2:
        return {row[0]: row[1] for row in lines}
    else:
        choices = sorted_by_pinyin([row[0] for row in lines])
        return {row[0]: row[1] for row in lines}, gr.Dropdown.update(choices=choices)


def get_template_names():
    logger.debug("获取模板文件名列表")
    return get_file_names_by_pinyin(TEMPLATES_DIR, filetypes=[".csv", "json"])


def get_template_dropdown():
    logger.debug("获取模板下拉菜单")
    template_names = get_template_names()
    return gr.Dropdown.update(choices=template_names)


def get_template_content(templates, selection, original_system_prompt):
    logger.debug(f"应用模板中，选择为{selection}，原始系统提示为{original_system_prompt}")
    try:
        return templates[selection]
    except:
        return original_system_prompt


def reset_textbox():
    logger.debug("重置文本框")
    return gr.update(value="")


def reset_default():
    default_host = state.reset_api_host()
    retrieve_proxy("")
    return gr.update(value=default_host), gr.update(value=""), "API-Host 和代理已重置"


def change_api_host(host):
    state.set_api_host(host)
    msg = f"API-Host更改为了{host}"
    logger.info(msg)
    return msg


def change_proxy(proxy):
    retrieve_proxy(proxy)
    os.environ["HTTPS_PROXY"] = proxy
    msg = f"代理更改为了{proxy}"
    logger.info(msg)
    return msg


def hide_middle_chars(s):
    if s is None:
        return ""
    if len(s) <= 8:
        return s
    else:
        head = s[:4]
        tail = s[-4:]
        hidden = "*" * (len(s) - 8)
        return head + hidden + tail


def submit_key(key):
    key = key.strip()
    msg = f"API密钥更改为了{hide_middle_chars(key)}"
    logger.info(msg)
    return key, msg


def replace_today(prompt):
    today = datetime.datetime.today().strftime("%Y-%m-%d")
    return prompt.replace("{current_date}", today)


SERVER_GEO_IP_MSG = None
FETCHING_IP = False


def get_geoip():
    global SERVER_GEO_IP_MSG, FETCHING_IP

    # 如果已经获取了IP信息，则直接返回
    if SERVER_GEO_IP_MSG is not None:
        return SERVER_GEO_IP_MSG

    # 如果正在获取IP信息，则返回等待消息
    if FETCHING_IP:
        return i18n("IP地址信息正在获取中，请稍候...")

    # 定义一个内部函数用于在新线程中执行IP信息的获取
    def fetch_ip():
        global SERVER_GEO_IP_MSG, FETCHING_IP
        try:
            with retrieve_proxy():
                response = requests.get("https://ipapi.co/json/", timeout=5)
            data = response.json()
        except:
            data = {"error": True, "reason": "连接ipapi失败"}
        if "error" in data.keys():
            logger.warning(f"无法获取IP地址信息。\n{data}")
            SERVER_GEO_IP_MSG = i18n("你可以使用聊天功能。")
        else:
            country = data["country_name"]
            if country == "China":
                SERVER_GEO_IP_MSG = "**您的IP区域：中国。**"
            else:
                SERVER_GEO_IP_MSG = i18n("您的IP区域：") + f"{country}。"
            logger.info(SERVER_GEO_IP_MSG)
        FETCHING_IP = False

    # 设置正在获取IP信息的标志
    FETCHING_IP = True

    # 启动一个新线程来获取IP信息
    thread = threading.Thread(target=fetch_ip)
    thread.start()

    # 返回一个默认消息，真正的IP信息将由新线程更新
    return i18n("正在获取IP地址信息，请稍候...")


def find_n(lst, max_num):
    n = len(lst)
    total = sum(lst)

    if total < max_num:
        return n

    for i in range(len(lst)):
        if total - lst[i] < max_num:
            return n - i - 1
        total = total - lst[i]
    return 1


def start_outputing():
    logger.debug("显示取消按钮，隐藏发送按钮")
    return gr.Button.update(visible=False), gr.Button.update(visible=True)


def end_outputing():
    return (
        gr.Button.update(visible=True),
        gr.Button.update(visible=False),
    )


def cancel_outputing():
    logger.info("中止输出……")
    state.interrupt()


def transfer_input(inputs):
    # 一次性返回，降低延迟
    textbox = reset_textbox()
    outputing = start_outputing()
    return (
        inputs,
        gr.update(value=""),
        gr.Button.update(visible=False),
        gr.Button.update(visible=True),
    )


def update_tecdo():
    return gr.Markdown.update(value=i18n("done"))


def add_source_numbers(lst, source_name="Source", use_source=True):
    if use_source:
        return [
            f'[{idx + 1}]\t "{item[0]}"\n{source_name}: {item[1]}'
            for idx, item in enumerate(lst)
        ]
    else:
        return [f'[{idx + 1}]\t "{item}"' for idx, item in enumerate(lst)]


def add_details(lst):
    nodes = []
    for index, txt in enumerate(lst):
        brief = txt[:25].replace("\n", "")
        nodes.append(
            f"< details > <summary > {brief}... < /summary > <p > {txt} < /p > </details >")
    return nodes


def sheet_to_string(sheet, sheet_name=None):
    result = []
    for index, row in sheet.iterrows():
        row_string = ""
        for column in sheet.columns:
            row_string += f"{column}: {row[column]}, "
        row_string = row_string.rstrip(", ")
        row_string += "."
        result.append(row_string)
    return result


def excel_to_string(file_path):
    # 读取Excel文件中的所有工作表
    excel_file = pd.read_excel(file_path, engine="openpyxl", sheet_name=None)

    # 初始化结果字符串
    result = []

    # 遍历每一个工作表
    for sheet_name, sheet_data in excel_file.items():
        # 处理当前工作表并添加到结果字符串
        result += sheet_to_string(sheet_data, sheet_name=sheet_name)

    return result


def get_last_day_of_month(any_day):
    # The day 28 exists in every month. 4 days later, it's always next month
    next_month = any_day.replace(day=28) + datetime.timedelta(days=4)
    # subtracting the number of the current day brings us back one month
    return next_month - datetime.timedelta(days=next_month.day)


def get_model_source(model_name, alternative_source):
    if model_name == "gpt2-medium":
        return "https://huggingface.co/gpt2-medium"


def refresh_ui_elements_on_load(current_model, selected_model_name, user_name):
    current_model.set_user_identifier(user_name)
    return toggle_like_btn_visibility(selected_model_name), *current_model.auto_load()


def toggle_like_btn_visibility(selected_model_name):
    if selected_model_name == "xmchat":
        return gr.update(visible=True)
    else:
        return gr.update(visible=False)


def get_corresponding_file_type_by_model_name(selected_model_name):
    if selected_model_name in ["xmchat", "GPT4 Vision"]:
        return ["image"]
    else:
        return [".pdf", ".docx", ".pptx", ".epub", ".xlsx", ".txt", "text"]


def new_auto_history_filename(username):
    latest_file = get_first_history_name(username)
    if latest_file:
        with open(os.path.join(HISTORY_DIR, username, latest_file + ".json"),
                  "r",
                  encoding="utf-8",
                  ) as f:
            if len(f.read()) == 0:
                return latest_file
    now = i18n("新对话 ") + datetime.datetime.now().strftime("%m-%d %H-%M")
    return f"{now}.json"


def get_history_filepath(username):
    dirname = os.path.join(HISTORY_DIR, username)
    os.makedirs(dirname, exist_ok=True)
    latest_file = get_first_history_name(username)
    if not latest_file:
        latest_file = new_auto_history_filename(username)

    latest_file = os.path.join(dirname, latest_file)
    return latest_file


def beautify_err_msg(err_msg):
    if "insufficient_quota" in err_msg:
        return i18n("剩余配额不足")
    if "The model `gpt-4` does not exist" in err_msg:
        return i18n("你没有权限访问 GPT4")
    if "Resource not found" in err_msg:
        return i18n("请查看 config_example.json，配置 Azure OpenAI")
    return err_msg


def auth_from_conf(username, password):
    try:
        with open(config_file, encoding="utf-8") as f:
            conf = json.load(f)
        usernames, passwords = [i[0] for i in conf["users"]], [
            i[1] for i in conf["users"]
        ]
        if username in usernames:
            if passwords[usernames.index(username)] == password:
                return True
        return False
    except:
        return False


def get_files_hash(file_src=None, file_paths=None):
    if file_src:
        file_paths = [x.name for x in file_src]
    if file_paths is None:
        file_paths = []
    file_paths.sort(key=lambda x: os.path.basename(x))

    md5_hash = hashlib.md5()
    for file_path in file_paths:
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                md5_hash.update(chunk)

    return md5_hash.hexdigest()


def myprint(**args):
    print(args)


def replace_special_symbols(string, replace_string=" "):
    # 定义正则表达式，匹配所有特殊符号
    pattern = r"[!@#$%^&*()<>?/\|}{~:]"

    new_string = re.sub(pattern, replace_string, string)

    return new_string


class ConfigType(Enum):
    Bool = 1
    String = 2
    Password = 3
    Number = 4
    ListOfStrings = 5


class ConfigItem:
    def __init__(self, key, name, default=None, type=ConfigType.String) -> None:
        self.key = key
        self.name = name
        self.default = default
        self.type = type


def generate_prompt_string(config_item):
    if config_item.default is not None:
        return (
            i18n("请输入 ")
            + colorama.Fore.GREEN
            + i18n(config_item.name)
            + colorama.Style.RESET_ALL
            + i18n("，默认为 ")
            + colorama.Fore.GREEN
            + str(config_item.default)
            + colorama.Style.RESET_ALL
            + i18n("：")
        )
    else:
        return (
            i18n("请输入 ")
            + colorama.Fore.GREEN
            + i18n(config_item.name)
            + colorama.Style.RESET_ALL
            + i18n("：")
        )


def generate_result_string(config_item, config_value):
    return (
        i18n("你设置了 ")
        + colorama.Fore.CYAN
        + i18n(config_item.name)
        + colorama.Style.RESET_ALL
        + i18n(" 为: ")
        + config_value
    )


class SetupWizard:
    def __init__(self, file_path=config_file) -> None:
        self.config = {}
        self.file_path = file_path
        language = input(
            '请问是否需要更改语言？可选："auto", "zh_CN", "en_US", "ja_JP", "ko_KR", "sv_SE", "ru_RU", "vi_VN"\nChange the language? Options: "auto", "zh_CN", "en_US", "ja_JP", "ko_KR", "sv_SE", "ru_RU", "vi_VN"\n目前正在使用中文(zh_CN)\nCurrently using Chinese(zh_CN)\n如果需要，请输入你想用的语言的代码：\nIf you need, please enter the code of the language you want to use:')
        if language.lower() in ["auto", "zh_cn", "en_us", "ja_jp", "ko_kr", "sv_se", "ru_ru", "vi_vn"]:
            # 设置环境变量来改变语言
            os.environ["LANGUAGE"] = language
        else:
            print(
                "你没有输入有效的语言代码，将使用默认语言中文(zh_CN)\nYou did not enter a valid language code, the default language Chinese(zh_CN) will be used.")
        print(i18n("正在进行首次设置，请按照提示进行配置，配置将会被保存在")
              + " config.json "
              + i18n("中。")
              )
        print(
            i18n("在")
            + " example_config.json "
            + i18n("中，包含了可用设置项及其简要说明。")
        )
        print(i18n("现在开始进行交互式配置。碰到不知道该怎么办的设置项时，请直接按回车键跳过，程序会自动选择合适的默认值。")
              )

    def set(self, config_items: List[ConfigItem], prompt: str):
        """Ask for a settings key
        Returns:
            Bool: Set or aborted
        """
        print(colorama.Fore.YELLOW + i18n(prompt) + colorama.Style.RESET_ALL)
        choice = input(i18n("输入 Yes(y) 或 No(n)，默认No："))
        if choice.lower() in ["y", "yes"]:
            for config_item in config_items:
                if config_item.type == ConfigType.Password:
                    config_value = getpass.getpass(
                        generate_prompt_string(config_item))
                    print(
                        colorama.Fore.CYAN
                        + i18n(config_item.name)
                        + colorama.Style.RESET_ALL
                        + ": "
                        + hide_middle_chars(config_value)
                    )
                    self.config[config_item.key] = config_value
                elif config_item.type == ConfigType.String:
                    config_value = input(generate_prompt_string(config_item))
                    print(generate_result_string(config_item, config_value))
                    self.config[config_item.key] = config_value
                elif config_item.type == ConfigType.Number:
                    config_value = input(generate_prompt_string(config_item))
                    print(generate_result_string(config_item, config_value))
                    try:
                        self.config[config_item.key] = int(config_value)
                    except:
                        print("输入的不是数字，将使用默认值。")
                elif config_item.type == ConfigType.ListOfStrings:
                    # read one string at a time
                    config_value = []
                    while True:
                        config_value_item = input(
                            generate_prompt_string(
                                config_item) + i18n("，输入空行结束：")
                        )
                        if config_value_item == "":
                            break
                        config_value.append(config_value_item)
                    print(generate_result_string(
                        config_item, ", ".join(config_value)))
                    self.config[config_item.key] = config_value
                elif config_item.type == ConfigType.Bool:
                    self.config[config_item.key] = True
            return True
        elif choice.lower() in ["n", "no"]:
            for config_item in config_items:
                print(
                    i18n("你选择了不设置 ")
                    + colorama.Fore.RED
                    + i18n(config_item.name)
                    + colorama.Style.RESET_ALL
                    + i18n("。")
                )
                if config_item.default is not None:
                    self.config[config_item.key] = config_item.default
            if type == ConfigType.Bool:
                return True
            return False

    def set_users(self):
        # 询问设置用户账户
        choice = input(colorama.Fore.YELLOW + i18n(
            "是否设置用户账户？设置后，用户需要登陆才可访问。输入 Yes(y) 或 No(n)，默认No：") + colorama.Style.RESET_ALL)
        if choice.lower() in ["y", "yes"]:
            users = []
            while True:
                username = input(i18n("请先输入用户名，输入空行结束添加用户："))
                if username == "":
                    break
                password = getpass.getpass(i18n("请输入密码："))
                users.append([username, password])
            self.config["users"] = users
            return True
        else:
            print(i18n("你选择了不设置用户账户。"))
            return False

    def __setitem__(self, setting_key: str, value):
        self.config[setting_key] = value

    def __getitem__(self, setting_key: str):
        return self.config[setting_key]

    def save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)


def setup_wizard():
    if not os.path.exists(config_file):
        wizard = SetupWizard()
        flag = False
        # 设置openai_api_key。
        flag = wizard.set(
            [ConfigItem("openai_api_key", "OpenAI API Key",
                        type=ConfigType.Password)],
            "是否设置默认 OpenAI API Key？如果设置，软件启动时会自动加载该API Key，无需在 UI 中手动输入。如果不设置，可以在软件启动后手动输入 API Key。",
        )
        if not flag:
            flag = wizard.set(
                [
                    ConfigItem(
                        "openai_api_key", "OpenAI API Key", type=ConfigType.Password
                    )
                ],
                "如果不设置，将无法使用GPT模型和知识库在线索引功能。如果不设置此选项，您必须每次手动输入API Key。如果不设置，将自动启用本地编制索引的功能，可与本地模型配合使用。请问要设置默认 OpenAI API Key 吗？",
            )
            if not flag:
                wizard["local_embedding"] = True
        # 设置openai_api_base
        wizard.set(
            [ConfigItem("openai_api_base", "OpenAI API Base",
                        type=ConfigType.String)],
            "是否设置默认 OpenAI API Base？如果你在使用第三方API或者CloudFlare Workers等来中转OpenAI API，可以在这里设置。",
        )
        # 设置http_proxy
        flag = wizard.set(
            [ConfigItem("http_proxy", "HTTP 代理", type=ConfigType.String)],
            "是否设置默认 HTTP 代理？这可以透过代理使用OpenAI API。",
        )
        if flag:
            wizard["https_proxy"] = wizard["http_proxy"]
        # 设置多 API Key 切换
        flag = wizard.set(
            [ConfigItem("api_key_list", "API Key 列表",
                        type=ConfigType.ListOfStrings)],
            "是否设置多 API Key 切换？如果设置，将在多个API Key之间切换使用。",
        )
        if flag:
            wizard["multi_api_key"] = True
        # 设置local_embedding
        wizard.set(
            [ConfigItem("local_embedding", "本地编制索引", type=ConfigType.Bool)],
            "是否在本地编制知识库索引？如果是，可以在使用本地模型时离线使用知识库，否则使用OpenAI服务来编制索引（需要OpenAI API Key）。请确保你的电脑有至少16GB内存。本地索引模型需要从互联网下载。",
        )
        print(
            colorama.Back.GREEN +
            i18n("现在开始设置其他在线模型的API Key") + colorama.Style.RESET_ALL
        )

        # Azure OpenAI
        wizard.set(
            [
                ConfigItem(
                    "azure_openai_api_key",
                    "Azure OpenAI API Key",
                    type=ConfigType.Password,
                ),
                ConfigItem(
                    "azure_openai_api_base_url",
                    "Azure OpenAI API Base URL",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "azure_openai_api_version",
                    "Azure OpenAI API Version",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "azure_deployment_name",
                    "Azure OpenAI Chat 模型 Deployment 名称",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "azure_embedding_deployment_name",
                    "Azure OpenAI Embedding 模型 Deployment 名称",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "azure_embedding_model_name",
                    "Azure OpenAI Embedding 模型名称",
                    type=ConfigType.String,
                ),
            ],
            "是否设置 Azure OpenAI？如果设置，软件启动时会自动加载该API Key，无需在 UI 中手动输入。如果不设置，将无法使用 Azure OpenAI 模型。",
        )
        print(
            colorama.Back.GREEN +
            i18n("现在开始进行软件功能设置") + colorama.Style.RESET_ALL
        )
        # 用户列表
        wizard.set_users()
        # 未登录情况下是否不展示对话历史
        wizard.set(
            [
                ConfigItem(
                    "hide_history_when_not_logged_in",
                    "未登录情况下是否不展示对话历史",
                    type=ConfigType.Bool,
                )
            ],
            "是否设置未登录情况下是否不展示对话历史？如果设置，未登录情况下将不展示对话历史。",
        )
        # 默认模型
        wizard.set(
            [
                ConfigItem(
                    "default_model",
                    "默认模型",
                    type=ConfigType.String,
                    default="gpt-3.5-turbo",
                )
            ],
            "是否更改默认模型？如果设置，软件启动时会自动加载该模型，无需在 UI 中手动选择。目前的默认模型为 GPT3.5 Turbo。可选的在线模型有："
            + "\n"
            + "\n".join(ONLINE_MODELS)
            + "\n"
            + "可选的本地模型为："
            + "\n"
            + "\n".join(LOCAL_MODELS),
        )
        # 是否启用自动加载
        wizard.set(
            [
                ConfigItem(
                    "hide_history_when_not_logged_in",
                    "是否不展示对话历史",
                    type=ConfigType.Bool,
                    default=False,
                )
            ],
            "未设置用户名/密码情况下是否不展示对话历史？",
        )
        # 如何自动命名对话历史
        wizard.set(
            [
                ConfigItem(
                    "chat_name_method_index",
                    "自动命名对话历史的方式（0: 使用日期时间命名；1: 使用第一条提问命名，2: 使用模型自动总结。）",
                    type=ConfigType.Number,
                    default=2,
                )
            ],
            "是否选择自动命名对话历史的方式？",
        )
        # 头像
        wizard.set(
            [
                ConfigItem(
                    "bot_avatar",
                    "机器人头像",
                    type=ConfigType.String,
                    default="default",
                ),
                ConfigItem(
                    "user_avatar",
                    "用户头像",
                    type=ConfigType.String,
                    default="default",
                ),
            ],
            '是否设置机器人头像和用户头像？可填写本地或网络图片链接，或者"none"（不显示头像）。',
        )
        # 川虎助理
        wizard.set(
            [
                ConfigItem(
                    "default_tecdo_assistant_model",
                    "川虎助理使用的模型",
                    type=ConfigType.String,
                    default="gpt-4",
                ),
                ConfigItem(
                    "GOOGLE_CSE_ID",
                    "谷歌搜索引擎ID（获取方式请看 https://stackoverflow.com/questions/37083058/programmatically-searching-google-in-python-using-custom-search）",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "GOOGLE_API_KEY",
                    "谷歌API Key（获取方式请看 https://stackoverflow.com/questions/37083058/programmatically-searching-google-in-python-using-custom-search）",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "WOLFRAM_ALPHA_APPID",
                    "Wolfram Alpha API Key（获取方式请看 https://products.wolframalpha.com/api/）",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "SERPAPI_API_KEY",
                    "SerpAPI API Key（获取方式请看 https://serpapi.com/）",
                    type=ConfigType.String,
                ),
            ],
            "是否设置川虎助理？如果不设置，仍可设置川虎助理。如果设置，可以使用川虎助理Pro模式。",
        )
        # 文档处理与显示
        wizard.set(
            [
                ConfigItem(
                    "latex_option",
                    "LaTeX 公式渲染策略",
                    type=ConfigType.String,
                    default="default",
                )
            ],
            '是否设置文档处理与显示？可选的 LaTeX 公式渲染策略有："default", "strict", "all"或者"disabled"。',
        )
        # 是否隐藏API Key输入框
        wizard.set(
            [
                ConfigItem(
                    "hide_my_key",
                    "是否隐藏API Key输入框",
                    type=ConfigType.Bool,
                    default=False,
                )
            ],
            "是否隐藏API Key输入框？如果设置，将不会在 UI 中显示API Key输入框。",
        )
        # 是否指定可用模型列表
        wizard.set(
            [
                ConfigItem(
                    "available_models",
                    "可用模型列表",
                    type=ConfigType.ListOfStrings,
                )
            ],
            "是否指定可用模型列表？如果设置，将只会在 UI 中显示指定的模型。默认展示所有模型。可用的模型有："
            + "\n".join(ONLINE_MODELS)
            + "\n".join(LOCAL_MODELS),
        )
        # 添加模型到列表
        wizard.set(
            [
                ConfigItem(
                    "extra_models",
                    "额外模型列表",
                    type=ConfigType.ListOfStrings,
                )
            ],
            "是否添加模型到列表？例如，训练好的GPT模型可以添加到列表中。可以在UI中自动添加模型到列表。",
        )
        # 分享
        wizard.set(
            [
                ConfigItem(
                    "server_name",
                    "服务器地址，例如设置为 0.0.0.0 则可以通过公网访问（如果你用公网IP）",
                    type=ConfigType.String,
                ),
                ConfigItem(
                    "server_port",
                    "服务器端口",
                    type=ConfigType.Number,
                    default=7860,
                ),
            ],
            "是否配置运行地址和端口？（不建议设置）",
        )
        wizard.set(
            [
                ConfigItem(
                    "share",
                    "是否通过gradio分享？",
                    type=ConfigType.Bool,
                    default=False,
                )
            ],
            "是否通过gradio分享？可以通过公网访问。",
        )
        wizard.save()
        print(colorama.Back.GREEN + i18n("设置完成。现在请重启本程序。") +
              colorama.Style.RESET_ALL)
        exit()


def save_pkl(data, file_path):
    with open(file_path, 'wb') as f:
        pickle.dump(data, f)


def load_pkl(file_path):
    with open(file_path, 'rb') as f:
        data = pickle.load(f)
    return data


def chinese_preprocessing_func(text: str) -> List[str]:
    import jieba
    jieba.setLogLevel('ERROR')
    return jieba.lcut(text)


def set_language_by_country(country: str) -> str:
    # 通过map来获取
    language_map = {
        "CN": "zh",
        "US": "en",
        "SG": "en",
        "MY": "en",
        "HK": "en",
    }
    return language_map.get(country, "en")


def get_history_from_chatbot(chatbot):
    # 如果chatbot的原始包含<div>则需要先进行处理，否则直接返回
    chat_history = []
    for message_pair in chatbot:
        user_message = html_to_text(message_pair[0])
        bot_message = html_to_text(message_pair[1])
        chat_history.append([user_message, bot_message])

    return chat_history
