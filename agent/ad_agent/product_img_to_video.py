from pydantic import BaseModel, Field


class ProductImgToVideoState(BaseModel):
    product: str = Field(description="商品名称")
    product_info: str = Field(description="商品信息")
    product_selling_point: list[str] = Field(description="商品卖点")
    product_img_path: list[str] = Field(description="商品图片path列表")
    video_fragment_duration: int = 5
    video_output_path: str = Field(description="视频输出path")
