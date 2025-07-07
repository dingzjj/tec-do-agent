from agent.ad_agent.prompt import ANALYSE_IMAGE_RESPONSE_SCHEMA


def reconstruct_model_image_info(model_image_info: dict) -> str:
    return f"""{ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["connection"]["description"]}:{model_image_info["connection"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["composition"]["description"]}:{model_image_info["composition"]}
    {ANALYSE_IMAGE_RESPONSE_SCHEMA["properties"]["Character posture"]["description"]}:{model_image_info["Character posture"]}
    """
