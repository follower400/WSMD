# data/data_processor.py

import re
from typing import List, Optional


def clean_text(text: str) -> str:
    """
    清洗文本，去除多余空白、特殊字符等

    Args:
        text: 原始文本字符串

    Returns:
        清洗后的文本字符串
    """
    if not text or not isinstance(text, str):
        return ""

    # 去除开头和结尾的空白字符
    text = text.strip()

    # 将多个连续的空格、制表符等替换为单个空格
    text = re.sub(r'\s+', ' ', text)

    # 去除控制字符（保留换行符、回车符、制表符等常用字符）
    # 去除其他控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # 统一换行符：将不同的换行符统一为 \n
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 去除连续的空行（将多个换行符替换为两个换行符）
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # 去除全角空格等特殊空白字符
    text = text.replace('\u3000', ' ')  # 全角空格替换为半角空格
    text = text.replace('\xa0', ' ')  # 不换行空格替换为普通空格

    # 再次清理可能产生的多余空格
    text = re.sub(r' +', ' ', text)

    return text


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 0) -> List[str]:
    """
    将文本按指定字符数切分成块

    Args:
        text: 待切分的文本字符串
        chunk_size: 每个块的最大字符数，默认512
        overlap: 块之间的重叠字符数，默认0（无重叠）

    Returns:
        文本块列表
    """
    if not text or not isinstance(text, str):
        return []

    if chunk_size <= 0:
        raise ValueError(f"chunk_size 必须大于0，当前值: {chunk_size}")

    if overlap < 0:
        raise ValueError(f"overlap 不能为负数，当前值: {overlap}")

    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) 必须小于 chunk_size ({chunk_size})")

    # 如果文本长度小于等于分块大小，直接返回
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        # 计算当前块的结束位置
        end = start + chunk_size

        # 如果已经到达或超过文本末尾
        if end >= text_length:
            chunks.append(text[start:])
            break

        # 尝试在边界附近找到合适的切分点（优先在句子边界切分）
        # 查找最近的句子结束符（。！？；）或换行符
        chunk_text = text[start:end]

        # 如果当前块不是以句子结束符结尾，尝试回退到上一个句子结束符
        if end < text_length:
            # 检查是否在合适的边界位置
            # 定义句子结束符和分隔符
            separators = ['。', '！', '？', '；', '：', '\n', '.', '!', '?', ';', ':']

            # 在最后100个字符内查找分隔符（避免回退过多）
            search_start = max(start, end - 100)
            last_separator_pos = -1

            for sep in separators:
                # 在块内查找最后一个分隔符的位置
                pos = chunk_text.rfind(sep)
                if pos != -1 and pos > last_separator_pos:
                    last_separator_pos = pos

            # 如果找到了合适的分隔符，且不是太靠近开头
            if last_separator_pos > chunk_size * 0.3:  # 至少保留30%的内容
                # 调整结束位置到分隔符后
                end = start + last_separator_pos + 1
                chunk_text = text[start:end]

        chunks.append(chunk_text)

        # 计算下一个块的起始位置（考虑重叠）
        start = end - overlap if overlap > 0 else end

        # 避免无限循环
        if start >= text_length:
            break

    # 清理每个块的内容（可选）
    chunks = [clean_text(chunk) for chunk in chunks]

    return chunks


def process_document(text: str, chunk_size: int = 512, overlap: int = 0,
                     clean_first: bool = True) -> List[str]:
    """
    完整的文档处理流程：清洗 + 分块

    Args:
        text: 原始文本字符串
        chunk_size: 每个块的最大字符数，默认512
        overlap: 块之间的重叠字符数，默认0
        clean_first: 是否在分块前先清洗文本，默认True

    Returns:
        处理后的文本块列表
    """
    if not text:
        return []

    # 清洗文本
    if clean_first:
        text = clean_text(text)

    # 分块
    chunks = chunk_text(text, chunk_size, overlap)

    return chunks


# 示例用法和测试
if __name__ == "__main__":
    # 测试文本清洗
    test_text = """
    这是一个    测试文本！
    包含多余的空格和

    空行。

    还有\x00控制字符需要清理。\r\n
    以及全角空格　这里。
    """

    print("=" * 50)
    print("测试文本清洗:")
    print("=" * 50)
    cleaned = clean_text(test_text)
    print(f"原始文本长度: {len(test_text)}")
    print(f"清洗后长度: {len(cleaned)}")
    print(f"清洗结果: {cleaned}")
    print()

    # 测试分块
    long_text = "这是一个很长的测试文本。" * 50
    print("=" * 50)
    print("测试分块 (chunk_size=512, overlap=0):")
    print("=" * 50)
    chunks = chunk_text(long_text, chunk_size=512, overlap=0)
    print(f"原始文本长度: {len(long_text)}")
    print(f"分块数量: {len(chunks)}")
    for i, chunk in enumerate(chunks[:3]):  # 只显示前3块
        print(f"块 {i + 1} 长度: {len(chunk)}")
    print()

    # 测试带重叠的分块
    print("=" * 50)
    print("测试分块 (chunk_size=100, overlap=20):")
    print("=" * 50)
    text_with_overlap = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
    chunks_overlap = chunk_text(text_with_overlap, chunk_size=100, overlap=20)
    print(f"原始文本长度: {len(text_with_overlap)}")
    print(f"分块数量: {len(chunks_overlap)}")
    for i, chunk in enumerate(chunks_overlap[:3]):
        print(f"块 {i + 1} 前30字符: {chunk[:30]}...")
    print()

    # 测试完整处理流程
    print("=" * 50)
    print("测试完整处理流程:")
    print("=" * 50)
    result = process_document(test_text, chunk_size=200, overlap=10)
    print(f"处理后的块数: {len(result)}")
    for i, chunk in enumerate(result):
        print(f"\n块 {i + 1} (长度: {len(chunk)}):")
        print(f"{chunk[:100]}...")