"""
基础法律文档加载器
从本地JSON文件读取法律条文和案例，转换为LlamaIndex Document对象
优化版本：增强问答对识别、改进文档类型推断、提升内容提取质量
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from llama_index.core import Document
import logging
from datetime import datetime
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class SimpleLegalDocumentLoader:
    """增强版法律文档加载器"""
    
    def __init__(self, data_path: str = None, verbose: bool = True):
        """
        初始化文档加载器
        
        Args:
            data_path: JSON数据文件路径，默认为指定路径
            verbose: 是否启用详细日志
        """
        if data_path is None:
            data_path = "./data/raw/knowledge_data"
        
        self.data_path = Path(data_path)
        self.verbose = verbose
        
        # 验证路径是否存在
        if not self.data_path.exists():
            logger.error(f"数据路径不存在: {self.data_path}")
            raise FileNotFoundError(f"数据路径不存在: {self.data_path}")
        
        if not self.data_path.is_dir():
            logger.error(f"数据路径不是目录: {self.data_path}")
            raise ValueError(f"数据路径不是目录: {self.data_path}")
        
        if verbose:
            logger.info(f"文档加载器已初始化，数据路径: {self.data_path}")
    
    def load_all_documents(self, max_files: int = None) -> List[Document]:
        """
        加载指定路径下的所有JSON文件
        
        Args:
            max_files: 最大加载文件数量，None表示加载所有
            
        Returns:
            文档对象列表
        """
        documents = []
        total_files_loaded = 0
        
        # 查找所有JSON文件
        json_files = list(self.data_path.glob("*.json"))
        json_files.sort()  # 按文件名排序，确保一致性
        
        if not json_files:
            logger.warning(f"在 {self.data_path} 中未找到JSON文件")
            return documents
        
        if self.verbose:
            logger.info(f"找到 {len(json_files)} 个JSON文件")
        
        # 限制加载的文件数量
        if max_files and max_files < len(json_files):
            json_files = json_files[:max_files]
            logger.info(f"将加载前 {max_files} 个文件")
        
        # 遍历并加载每个JSON文件
        for i, json_file in enumerate(json_files, 1):
            if self.verbose:
                logger.info(f"正在处理文件 [{i}/{len(json_files)}]: {json_file.name}")
            
            try:
                file_docs = self.load_json_file(json_file)
                documents.extend(file_docs)
                total_files_loaded += 1
                
                if self.verbose and file_docs:
                    logger.info(f"  √ 已加载 {len(file_docs)} 个文档")
            except Exception as e:
                logger.error(f"处理文件失败 {json_file.name}: {e}")
                if self.verbose:
                    logger.debug(f"错误详情: {str(e)}")
        
        if self.verbose:
            logger.info(f"完成！成功加载 {total_files_loaded} 个文件，共 {len(documents)} 个文档")
            
            # 统计文档类型
            if documents:
                type_count = {}
                for doc in documents:
                    doc_type = doc.metadata.get("doc_type", "unknown")
                    type_count[doc_type] = type_count.get(doc_type, 0) + 1
                
                logger.info("文档类型统计:")
                for doc_type, count in type_count.items():
                    logger.info(f"  {doc_type}: {count} 个文档")
        
        return documents
    
    def load_json_file(self, file_path: Path) -> List[Document]:
        """
        加载单个JSON文件
        
        Args:
            file_path: JSON文件路径
            
        Returns:
            文档对象列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if self.verbose:
                logger.debug(f"成功读取文件: {file_path.name}, 数据大小: {len(str(data))} 字节")
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败 {file_path}: {e}")
            return []
        except UnicodeDecodeError as e:
            logger.error(f"编码错误 {file_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"读取文件失败 {file_path}: {e}")
            return []
        
        documents = []
        file_name = file_path.name
        
        # 根据JSON结构解析文档
        if isinstance(data, list):
            # 处理数组类型的JSON
            if self.verbose:
                logger.debug(f"处理数组类型数据，共 {len(data)} 个元素")
            
            for idx, item in enumerate(data):
                doc = self._json_to_document(item, file_name, item_index=idx)
                if doc:
                    documents.append(doc)
                    
        elif isinstance(data, dict):
            # 处理对象类型的JSON
            if self.verbose:
                logger.debug(f"处理对象类型数据，共 {len(data)} 个键")
            
            doc = self._json_to_document(data, file_name)
            if doc:
                documents.append(doc)
        else:
            logger.warning(f"不支持的数据类型 {type(data).__name__} 在文件 {file_name}")
        
        return documents
    
    def _json_to_document(self, data: Dict[str, Any], file_name: str, 
                         item_index: int = None) -> Optional[Document]:
        """
        将JSON数据转换为Document对象
        
        Args:
            data: JSON数据
            file_name: 源文件名
            item_index: 在数组中的索引位置（如果适用）
            
        Returns:
            Document对象，如果转换失败则返回None
        """
        if not isinstance(data, dict):
            if self.verbose:
                logger.debug(f"跳过非字典类型的数据: {type(data).__name__}")
            return None
        
        # 跳过空数据
        if not data:
            if self.verbose:
                logger.debug("跳过空数据字典")
            return None
        
        # 提取文档内容
        content = self._extract_content(data)
        if not content or not content.strip():
            if self.verbose:
                logger.debug("跳过无内容的数据")
            return None
        
        # 提取元数据
        metadata = self._extract_metadata(data, file_name, item_index)
        
        # 创建Document对象
        try:
            doc = Document(
                text=content,
                metadata=metadata
            )
            
            # 添加额外信息
            doc.extra_info = {
                "created_at": datetime.now().isoformat(),
                "content_length": len(content),
                "word_count": len(content.split())
            }
            
            return doc
            
        except Exception as e:
            logger.error(f"创建Document对象失败: {e}")
            if self.verbose:
                logger.debug(f"失败数据: {data}")
            return None
    
    def _extract_content(self, data: Dict[str, Any]) -> str:
        """
        从JSON数据中提取文本内容
        
        Args:
            data: JSON数据
            
        Returns:
            文本内容字符串
        """
        # 优先处理问答对格式（根据您的实际数据结构）
        if "input" in data and "output" in data:
            input_text = str(data.get("input", "")).strip()
            output_text = str(data.get("output", "")).strip()
            
            if input_text and output_text:
                return f"问题: {input_text}\n回答: {output_text}"
            elif input_text:
                return input_text
            elif output_text:
                return output_text
        
        # 常见的内容字段名称（扩展列表）
        content_fields = [
            "content", "text", "body", "description", "summary", 
            "facts", "reasoning", "judgment", "title", "name",
            "question", "answer", "query", "response",  # 问答相关
            "abstract", "introduction", "conclusion",  # 论文相关
            "content_text", "document", "article",  # 文档相关
        ]
        
        # 尝试从常见字段获取内容
        for field in content_fields:
            if field in data and data[field]:
                field_value = data[field]
                if isinstance(field_value, str) and field_value.strip():
                    return field_value.strip()
                elif isinstance(field_value, (int, float, bool)):
                    return str(field_value)
        
        # 如果没有明确的内容字段，尝试合并所有文本字段
        content_parts = []
        for key, value in data.items():
            if isinstance(value, str) and value.strip():
                # 跳过明确的元数据字段
                metadata_fields = [
                    "id", "date", "author", "category", "type", "source",
                    "file", "url", "link", "index", "order", "no", "number",
                    "created_at", "updated_at", "timestamp", "time"
                ]
                
                if key.lower() not in [f.lower() for f in metadata_fields]:
                    # 对长文本进行简化
                    simplified_text = value.strip()
                    if len(simplified_text) > 500:
                        simplified_text = simplified_text[:500] + "..."
                    content_parts.append(f"{key}: {simplified_text}")
                    
            elif isinstance(value, (int, float, bool)):
                content_parts.append(f"{key}: {value}")
        
        if content_parts:
            return "\n".join(content_parts)
        
        # 如果没有任何文本内容，返回空字符串
        return ""
    
    def _extract_metadata(self, data: Dict[str, Any], file_name: str, 
                         item_index: int = None) -> Dict[str, Any]:
        """
        从JSON数据中提取元数据
        
        Args:
            data: JSON数据
            file_name: 源文件名
            item_index: 在数组中的索引位置
            
        Returns:
            元数据字典
        """
        metadata = {
            "source": str(file_name),
            "file_name": file_name,
            "data_type": type(data).__name__,
        }
        
        # 如果是在数组中，添加索引信息
        if item_index is not None:
            metadata["item_index"] = item_index
        
        # 扩展的元数据字段列表
        metadata_fields = [
            "id", "title", "name", "date", "author", "category", 
            "type", "law_name", "article_no", "case_id", "case_name", 
            "court", "year", "tags", "keywords", "topic", "subject",
            "input", "output", "question", "answer",  # 问答相关
            "source_url", "url", "link",  # 链接相关
            "page", "section", "chapter",  # 文档结构
            "created_at", "updated_at", "timestamp",  # 时间相关
        ]
        
        for field in metadata_fields:
            if field in data and data[field]:
                value = data[field]
                if isinstance(value, (str, int, float, bool)):
                    metadata[field] = value
                else:
                    metadata[field] = str(value)
        
        # 清理和规范化元数据
        self._clean_metadata(metadata)
        
        # 推断文档类型
        metadata["doc_type"] = self._infer_doc_type(data)
        
        # 添加文档质量标记
        metadata["has_content"] = bool(data.get("content") or data.get("text") or data.get("input"))
        metadata["has_metadata"] = len(metadata) > 3  # 除了基本字段外的元数据
        
        return metadata
    
    def _clean_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        清理和规范化元数据
        
        Args:
            metadata: 元数据字典
        """
        # 清理字符串类型的元数据
        for key, value in list(metadata.items()):
            if isinstance(value, str):
                # 去除前后空格
                cleaned = value.strip()
                # 如果清理后为空，删除该字段
                if not cleaned:
                    del metadata[key]
                else:
                    metadata[key] = cleaned
    
    def _infer_doc_type(self, data: Dict[str, Any]) -> str:
        """
        推断文档类型
        
        Args:
            data: JSON数据
            
        Returns:
            文档类型字符串
        """
        # 1. 检查问答对特征（优先）
        if "input" in data and "output" in data:
            return "qa_pair"
        elif "question" in data and "answer" in data:
            return "qa_pair"
        elif "query" in data and "response" in data:
            return "qa_pair"
        
        # 2. 检查法律条文特征
        law_keywords = ["law_name", "article_no", "条文", "条款", "法条", "法规", "条例"]
        if any(keyword in data for keyword in law_keywords):
            return "law_article"
        
        # 3. 检查案例特征
        case_keywords = ["case_id", "case_name", "court", "案件", "判决", "案例", "裁判", "法院"]
        if any(keyword in data for keyword in case_keywords):
            return "legal_case"
        
        # 4. 检查是否包含articles字段
        if "articles" in data and isinstance(data["articles"], list):
            return "law_collection"
        
        # 5. 检查是否包含cases字段
        if "cases" in data and isinstance(data["cases"], list):
            return "case_collection"
        
        # 6. 基于内容推断
        content_str = str(data).lower()
        if any(keyword in content_str for keyword in ["法律", "法规", "条文", "法条"]):
            return "law_related"
        elif any(keyword in content_str for keyword in ["案例", "案件", "判决", "法院"]):
            return "case_related"
        
        return "general"
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取加载器统计信息
        
        Returns:
            统计信息字典
        """
        json_files = list(self.data_path.glob("*.json"))
        
        stats = {
            "data_path": str(self.data_path),
            "total_json_files": len(json_files),
            "file_list": [f.name for f in json_files],
            "supported_extensions": [".json"],
        }
        
        return stats


# 便捷函数
def load_legal_documents(data_path: str = None, max_files: int = None, 
                        verbose: bool = True) -> List[Document]:
    """
    快速加载法律文档的便捷函数
    
    Args:
        data_path: 数据路径，默认为指定路径
        max_files: 最大加载文件数量
        verbose: 是否显示详细日志
        
    Returns:
        文档列表
    """
    loader = SimpleLegalDocumentLoader(data_path, verbose=verbose)
    return loader.load_all_documents(max_files=max_files)


def load_single_file(file_path: str, verbose: bool = True) -> List[Document]:
    """
    加载单个JSON文件
    
    Args:
        file_path: JSON文件完整路径
        verbose: 是否显示详细日志
        
    Returns:
        文档列表
    """
    # 创建临时加载器
    loader = SimpleLegalDocumentLoader(verbose=verbose)
    
    # 确保文件存在
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        logger.error(f"文件不存在: {file_path}")
        return []
    
    if file_path_obj.suffix.lower() != ".json":
        logger.warning(f"文件 {file_path} 不是JSON文件")
    
    return loader.load_json_file(file_path_obj)


def preview_document(doc: Document, max_length: int = 200) -> Dict[str, Any]:
    """
    预览文档内容
    
    Args:
        doc: Document对象
        max_length: 内容预览最大长度
        
    Returns:
        预览信息字典
    """
    preview = {
        "doc_type": doc.metadata.get("doc_type", "unknown"),
        "source": doc.metadata.get("source", "unknown"),
        "file_name": doc.metadata.get("file_name", "unknown"),
        "content_preview": doc.text[:max_length] + ("..." if len(doc.text) > max_length else ""),
        "content_length": len(doc.text),
        "word_count": len(doc.text.split()),
        "metadata_keys": list(doc.metadata.keys()),
    }
    
    return preview


# 使用示例
if __name__ == "__main__":
    print("=" * 60)
    print("基础法律文档加载器 - 增强版")
    print("=" * 60)
    
    try:
        # 示例1: 获取统计信息
        print("\n=== 示例1: 获取数据统计信息 ===")
        loader = SimpleLegalDocumentLoader(verbose=True)
        stats = loader.get_statistics()
        
        print(f"数据路径: {stats['data_path']}")
        print(f"找到 {stats['total_json_files']} 个JSON文件")
        print(f"文件列表: {', '.join(stats['file_list'])}")
        
        # 示例2: 加载所有文档
        print("\n=== 示例2: 加载所有文档 ===")
        documents = loader.load_all_documents()
        
        print(f"\n成功加载 {len(documents)} 个文档")
        
        if documents:
            # 统计文档类型
            type_count = {}
            for doc in documents:
                doc_type = doc.metadata.get("doc_type", "unknown")
                type_count[doc_type] = type_count.get(doc_type, 0) + 1
            
            print("\n文档类型统计:")
            for doc_type, count in sorted(type_count.items()):
                print(f"  {doc_type}: {count} 个文档 ({count/len(documents)*100:.1f}%)")
            
            # 显示前5个文档的预览
            print("\n=== 前5个文档预览 ===")
            for i, doc in enumerate(documents[:5]):
                print(f"\n文档 {i+1}:")
                preview = preview_document(doc)
                print(f"类型: {preview['doc_type']}")
                print(f"来源: {preview['file_name']}")
                print(f"内容长度: {preview['content_length']} 字符, {preview['word_count']} 词")
                print(f"元数据字段: {', '.join(preview['metadata_keys'])}")
                print(f"内容预览: {preview['content_preview']}")
                print("-" * 50)
    
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    
    # 示例3: 使用便捷函数
    print("\n=== 示例3: 使用便捷函数 ===")
    try:
        documents = load_legal_documents(verbose=True)
        print(f"\n通过便捷函数加载了 {len(documents)} 个文档")
        
        if documents:
            # 显示不同类型文档的示例
            doc_types = set([doc.metadata.get("doc_type", "unknown") for doc in documents])
            print(f"\n包含的文档类型: {', '.join(doc_types)}")
            
    except Exception as e:
        print(f"便捷函数加载失败: {e}")
    
    print("\n" + "=" * 60)
    print("文档加载完成！")