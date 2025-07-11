from config import conf
import time
import httpx
import asyncio


async def create_tt_avatar_task(api_key, secret_key, avatar_id, script_text):
    url = "https://dev01-ai-orchestration.tec-develop.cn/api/ai/tiktok/v1/tt-avatar/create-task"
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }
    payload = {
        "material_packages": [
            {
                "avatar_id": avatar_id,
                "script": script_text
            }
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        print(f"创建任务响应：{response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()
        task_id = data.get("data", {}).get("list", [])[0].get("task_id")
        return task_id


async def poll_task_status(api_key, secret_key, task_id, interval=30, max_wait=600):
    url = f"https://dev01-ai-orchestration.tec-develop.cn/api/ai/tiktok/v1/tt-avatar/get-task?task_ids={
        task_id}"
    headers = {
        "X-API-Key": api_key,
        "X-Secret-Key": secret_key,
        "Content-Type": "application/json"
    }

    start_time = time.time()
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                task_list = data.get("data", {}).get("list", [])
                if not task_list:
                    print("任务列表为空，重试中...")
                else:
                    status = task_list[0].get("status")
                    print(f"当前任务状态: {status}")

                    if status == "SUCCESS":
                        print("任务成功完成！")
                        return task_list[0].get("preview_url")
                    elif status == "FAILED":
                        print("任务失败。")
                        return None
                    elif status == "PROCESSING":
                        print("任务正在处理...")
                    elif status == "SUBMITED":
                        print("任务已提交，等待中...")
                    else:
                        print(f"未知状态: {status}")

            except Exception as e:
                print(f"请求或解析出错：{e}")

            if time.time() - start_time > max_wait:
                print("超时未完成任务。")
                return None

            await asyncio.sleep(interval)


async def create_tt_digital_human(text, digital_human_id="7393172244749811728"):
    api_key = conf.get("tiktok_api_key")
    secret_key = conf.get("tiktok_secret_key")
    task_id = await create_tt_avatar_task(api_key, secret_key, digital_human_id, text)
    result = await poll_task_status(api_key, secret_key, task_id)
    return result
