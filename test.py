from util.common_util import CommonUtil
import pandas as pd
from util.oss_util import OSSUtil 
oss = OSSUtil()

def process_urls_from_csv(file_path):
    """处理csv文件的url地址"""
    try:
        df = pd.read_csv(file_path)  # 读取 CSV 文件
        if 'site' not in df.columns:
            print("CSV 文件中未找到 'url' 列")
            return
        
        # 处理每个 URL
        for url in df['site']:
            test_get_name_by_url_domain_only(url)
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查路径。")
    except Exception as e:
        print(f"发生错误: {e}")

def test_get_name_by_url_domain_only(url):
    """测试生成网站名称的工具"""
    res = CommonUtil.get_name_by_url(url)
    print(f"原始 URL: {url}")
    print(f"处理后生成的名字: {res}")
    
# 手动生成图片
def upload_image_and_generate_thumbnail(png_path):
    """根据截图上传图片"""
    image_key = oss.get_default_file_key(png_path)
    original_image_key = oss.upload_file_to_r2(png_path, image_key)

    thumbnail_key = oss.generate_thumbnail_image(original_image_key,image_key)

    return original_image_key, thumbnail_key

original_image_key, thumbnail_key = upload_image_and_generate_thumbnail("./images/aimusicgenerator-me.png")
print(f"Original image uploaded to: {original_image_key}")
print(f"Thumbnail generated: {thumbnail_key}")


csv_file_path = './Data/all_website_data.csv'  # 请确保这个路径是正确的

# 处理 CSV 文件中的 URL
# process_urls_from_csv(csv_file_path)
