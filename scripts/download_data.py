# scripts/download_data.py
import os
import requests
import zipfile
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 数据集下载地址
DATASET_URL = "https://github.com/oneal2000/STARD/archive/refs/heads/main.zip"
TARGET_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def download_with_resume(url, target_path):
    """支持断点续传和自动重试的下载函数"""
    # 配置重试策略：最多重试5次
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    headers = {}
    # 获取已下载文件的大小，实现断点续传
    if os.path.exists(target_path):
        resume_pos = os.path.getsize(target_path)
        headers['Range'] = f'bytes={resume_pos}-'
    else:
        resume_pos = 0

    print(f"开始从 {url} 下载...")
    response = session.get(url, headers=headers, stream=True, timeout=30)

    if response.status_code in [200, 206]:
        total_size = int(response.headers.get('content-length', 0))
        mode = 'ab' if resume_pos > 0 else 'wb'
        with open(target_path, mode) as f:
            downloaded = resume_pos
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r下载进度: {progress:.1f}%", end="")
        print("\n下载完成！")
    else:
        raise Exception(f"下载失败，状态码: {response.status_code}")


def download_and_extract():
    os.makedirs(TARGET_DIR, exist_ok=True)
    zip_path = os.path.join(TARGET_DIR, "STARD-main.zip")

    download_with_resume(DATASET_URL, zip_path)

    print("正在解压...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(TARGET_DIR)

    os.remove(zip_path)
    print(f"✅ 数据集已准备就绪，位于 {TARGET_DIR}/STARD-main/")


if __name__ == "__main__":
    download_and_extract()