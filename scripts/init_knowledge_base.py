import os
import sys
from pathlib import Path
# 将项目根目录添加到 Python 路径
project_root = Path(__file__).parent.parent   # 指向 wisdom_mediator/
sys.path.insert(0, str(project_root))
import logging
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('init_knowledge_base.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)
# 现在可以正常导入 data 包下的模块
from data.vector_db import LegalVectorDB
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
import yaml
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import traceback


class KnowledgeBaseBuilder:
    """法律知识库构建器"""

    def _simple_chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """简单固定长度分块，优先在句末截断"""
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            # 尝试在标点处断开
            if end < text_len:
                for sep in ['。', '；', '！', '？', '\n', '；']:
                    last_sep = text.rfind(sep, start, end)
                    if last_sep > start + chunk_size // 2:
                        end = last_sep + 1
                        break
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start = end - overlap if end < text_len else text_len
        return chunks
    def __init__(self, config_path: str = None):
        """
        初始化知识库构建器
        
        Args:
            config_path: 配置文件路径，默认为 config/vector_db.yaml
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config",
                "vector_db.yaml"
            )
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
        
        # 初始化组件
        self.vector_db = None
        self.stard_adapter = None
        self.chunking_strategy = None
        self.content_validator = None
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"配置文件加载成功: {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            # 使用默认配置
            default_config = {
                "vector_db": {
                    "persist_directory": "./storage/chroma",  # 改成你的持久化目录
                    "collection_name": "legal_knowledge_v1",  # 改成你的集合名
                    "embedding_model": "BAAI/bge-small-zh-v1.5",
                    "device": "cpu",
                    "model_cache_directory": "./data/model_cache"
                },
                "data": {
                    "corpus_path": "./data/raw/knowledge_data/corpus.jsonl",
                    "chunk_size": 512,
                    "chunk_overlap": 50
                },
                "processing": {
                    "batch_size": 100,
                    "enable_validation": True,
                    "enable_backup": True
                }
            }
            logger.warning(f"使用默认配置")
            return default_config
    
    def _init_components(self):
        """初始化处理组件"""
        try:
            # 初始化向量数据库
            self.vector_db = LegalVectorDB(
                persist_directory=self.config["vector_db"]["persist_directory"],
                collection_name=self.config["vector_db"]["collection_name"],
                embedding_model=self.config["vector_db"]["embedding_model"],
                device=self.config["vector_db"]["device"],
                model_cache_directory=self.config["vector_db"]["model_cache_directory"]
            )
            logger.info("向量数据库初始化成功")
            
            # 初始化数据处理组件
            from core.legal_knowledge import (
                STARDAdapter, 
                LegalChunkingStrategy, 
                LegalContentValidator,
                build_chromadb_records
            )
            self.stard_adapter = STARDAdapter
            self.chunking_strategy = LegalChunkingStrategy
            self.content_validator = LegalContentValidator
            self.build_chromadb_records = build_chromadb_records
            logger.info("数据处理组件初始化成功")
            
        except ImportError as e:
            logger.error(f"模块导入失败: {e}")
            logger.error("请确保相关模块在Python路径中")
            raise
        except Exception as e:
            logger.error(f"组件初始化失败: {e}")
            raise
    
    def _infer_law_type(self, law_name: str) -> str:
        """
        推断法律类型
        从 legal_knowledge_search.py 适配而来
        
        Args:
            law_name: 法律名称
            
        Returns:
            法律类型: "法律"、"行政法规"、"司法解释"、"地方法规" 等
        """
        if not law_name:
            return "unknown"
        
        law_name_lower = law_name.lower()
        
        # 法律类型推断规则
        if any(keyword in law_name_lower for keyword in ["宪法", "民法典", "刑法", "诉讼法", "合同法", "劳动法"]):
            return "法律"
        elif "条例" in law_name_lower or "办法" in law_name_lower or "规定" in law_name_lower:
            if any(region in law_name for region in ["省", "市", "自治区", "州", "县"]):
                return "地方法规"
            else:
                return "行政法规"
        elif "解释" in law_name_lower or "批复" in law_name_lower or "规定" in law_name_lower:
            return "司法解释"
        elif any(region in law_name for region in ["省", "市", "自治区", "州", "县"]):
            return "地方法规"
        else:
            return "其他规范性文件"
    
    def _infer_dispute_type(self, law_name: str, content: str) -> List[str]:
        """
        推断纠纷类型
        基于法律名称和内容推断相关纠纷类型
        
        Args:
            law_name: 法律名称
            content: 法律条文内容
            
        Returns:
            纠纷类型列表
        """
        dispute_types = []
        text_for_analysis = (law_name or "") + " " + (content or "")
        
        # 纠纷类型关键词映射
        dispute_keywords = {
            "劳动纠纷": ["劳动", "用工", "工资", "加班", "解雇", "工伤", "劳动合同", "社保", "公积金"],
            "合同纠纷": ["合同", "协议", "违约", "履行", "解除", "终止", "定金", "违约金"],
            "民事纠纷": ["侵权", "赔偿", "人身损害", "财产", "继承", "婚姻", "家庭", "邻里"],
            "刑事纠纷": ["犯罪", "刑罚", "拘留", "逮捕", "侦查", "起诉", "审判", "量刑"],
            "行政纠纷": ["行政许可", "行政处罚", "行政复议", "行政诉讼", "政府", "机关", "行政行为"],
            "经济纠纷": ["金融", "证券", "保险", "银行", "贷款", "投资", "贸易", "商业"],
            "知识产权": ["专利", "商标", "版权", "著作权", "发明", "创意", "盗版", "侵权"],
        }
        
        for dispute_type, keywords in dispute_keywords.items():
            if any(keyword in text_for_analysis for keyword in keywords):
                dispute_types.append(dispute_type)
        
        # 默认类型
        if not dispute_types:
            dispute_types.append("一般民事纠纷")
        
        return dispute_types
    
    def _infer_jurisdiction(self, law_name: str) -> str:
        """
        推断适用地域
        
        Args:
            law_name: 法律名称
            
        Returns:
            适用地域
        """
        if not law_name:
            return "全国"
        
        # 检查是否包含地域信息
        regions = {
            "北京": ["北京市", "北京"],
            "上海": ["上海市", "上海"],
            "广东": ["广东省", "广东", "广州市", "深圳"],
            "江苏": ["江苏省", "江苏", "南京市", "苏州"],
            "浙江": ["浙江省", "浙江", "杭州市", "宁波"],
            "全国": ["中华人民共和国", "全国", "国家"]
        }
        
        for jurisdiction, keywords in regions.items():
            if any(keyword in law_name for keyword in keywords):
                return jurisdiction
        
        return "全国"
    
    def _enrich_chunk_metadata(self, chunk, original_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        丰富chunk的元数据
        
        Args:
            chunk: LegalChunk对象
            original_doc: 原始文档
            
        Returns:
            丰富后的元数据字典
        """
        metadata = {
            "law_name": chunk.law_name or original_doc.get("name", ""),
            "article_no": chunk.article_no or "",
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "source_doc_id": original_doc.get("id", ""),
        }
        
        # 推断法律类型
        metadata["law_type"] = self._infer_law_type(metadata["law_name"])
        
        # 推断纠纷类型
        metadata["dispute_type"] = self._infer_dispute_type(
            metadata["law_name"], 
            chunk.content
        )
        
        # 推断适用地域
        metadata["jurisdiction"] = self._infer_jurisdiction(metadata["law_name"])
        
        # 添加时间戳
        metadata["created_at"] = datetime.now().isoformat()
        metadata["version"] = "1.0"
        
        return metadata

    def _process_document(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """绕过复杂分块器，直接处理STARD文档"""
        chunks = []
        try:
            if not isinstance(doc, dict):
                return chunks

            # STARD实际字段: id (int), name (str), content (str)
            doc_id = str(doc.get("id", "unknown"))
            title = doc.get("name", "未知法规")
            content = doc.get("content", "")

            if not content or len(content.strip()) < 5:
                return chunks

            chunk_size = self.config["data"].get("chunk_size", 500)
            overlap = self.config["data"].get("chunk_overlap", 50)

            # 简单固定长度分块，尽量在句末截断
            text_chunks = []
            start = 0
            text_len = len(content)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                if end < text_len:
                    for sep in ['。', '；', '！', '？', '\n', ';']:
                        last_sep = content.rfind(sep, start, end)
                        if last_sep > start + chunk_size // 2:
                            end = last_sep + 1
                            break
                chunk = content[start:end].strip()
                if chunk:
                    text_chunks.append(chunk)
                start = end - overlap if end < text_len else text_len

            for i, chunk_text in enumerate(text_chunks):
                chunk_id = f"{doc_id}_chunk{i}"
                metadata = {
                    "source_doc_id": doc_id,
                    "title": title,
                    "law_type": self._infer_law_type(title),
                    "dispute_type": self._infer_dispute_type(title, chunk_text),
                    "jurisdiction": self._infer_jurisdiction(title),
                    "chunk_index": i,
                    "created_at": datetime.now().isoformat(),
                    "version": "1.0"
                }
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_text,
                    "metadata": metadata
                })
            # 加一个防御性判断，防止 doc_id 没取到
            logger.debug(f"文档 {doc_id or 'no_id'} 生成 {len(chunks)} 个chunks")

        except Exception as e:
            logger.error(f"处理文档失败: {e}")
        return chunks
    def build_from_stard_corpus(self, corpus_path: str = None) -> Dict[str, Any]:
        """
        从STARD语料库构建知识库
        
        Args:
            corpus_path: corpus.jsonl文件路径
            
        Returns:
            构建结果统计
        """
        if corpus_path is None:
            corpus_path = self.config["data"]["corpus_path"]
        
        corpus_path = Path(corpus_path)
        if not corpus_path.exists():
            logger.error(f"语料库文件不存在: {corpus_path}")
            raise FileNotFoundError(f"语料库文件不存在: {corpus_path}")
        
        logger.info(f"开始从STARD语料库构建知识库: {corpus_path}")
        
        all_chunks = []
        stats = {
            "total_docs": 0,
            "total_chunks": 0,
            "failed_docs": 0,
            "start_time": datetime.now(),
            "end_time": None,
            "duration": None
        }
        
        try:
            # 1. 初始化组件
            self._init_components()
            
            # 2. 流式读取并处理文档
            adapter = self.stard_adapter()
            
            for doc in adapter.iter_corpus(str(corpus_path)):
                stats["total_docs"] += 1
                
                # 处理文档
                chunks = self._process_document(doc)
                
                if chunks:
                    all_chunks.extend(chunks)
                    stats["total_chunks"] += len(chunks)
                    
                    # 批量处理
                    batch_size = self.config["processing"].get("batch_size", 100)
                    if len(all_chunks) >= batch_size:
                        self._save_chunks_to_vector_db(all_chunks)
                        all_chunks = []
                    
                    # 进度输出
                    if stats["total_docs"] % 10 == 0:
                        logger.info(f"已处理 {stats['total_docs']} 个文档，生成 {stats['total_chunks']} 个chunks")
                else:
                    stats["failed_docs"] += 1
                    logger.warning(f"文档 {doc.get('id', 'unknown')} 处理失败或未生成chunks")
            
            # 3. 处理剩余的chunks
            if all_chunks:
                self._save_chunks_to_vector_db(all_chunks)
            
            # 4. 记录统计信息
            stats["end_time"] = datetime.now()
            stats["duration"] = (stats["end_time"] - stats["start_time"]).total_seconds()
            
            logger.info(f"知识库构建完成!")
            logger.info(f"总计: {stats['total_docs']} 个文档, {stats['total_chunks']} 个chunks")
            logger.info(f"失败: {stats['failed_docs']} 个文档")
            logger.info(f"耗时: {stats['duration']:.2f} 秒")
            
            return stats
            
        except Exception as e:
            logger.error(f"构建知识库失败: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _save_chunks_to_vector_db(self, chunks: List[Dict[str, Any]]):
        """
        保存chunks到向量数据库
        
        Args:
            chunks: chunk列表
        """
        if not chunks or not self.vector_db:
            return
        
        try:
            # 调用向量数据库的add_documents方法
            result = self.vector_db.add_documents(chunks)
            
            logger.info(f"成功保存 {len(chunks)} 个chunks到向量数据库")
            logger.debug(f"保存结果: {result}")
            
        except Exception as e:
            logger.error(f"保存chunks到向量数据库失败: {e}")
            logger.error(traceback.format_exc())
    
    def build_from_json_files(self, data_dir: str = None):
        """
        从JSON文件构建知识库（备选方案）
        
        Args:
            data_dir: JSON文件目录
        """
        logger.warning("从JSON文件构建功能尚未完全实现，建议使用STARD语料库")
        # TODO: 实现JSON文件构建逻辑
        pass
    
    def clear_collection(self):
        """清空向量数据库集合"""
        try:
            if self.vector_db:
                self.vector_db.clear_collection()
                logger.info("向量数据库集合已清空")
        except Exception as e:
            logger.error(f"清空集合失败: {e}")
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        try:
            if self.vector_db:
                info = self.vector_db.get_collection_info()
                logger.info(f"集合信息: {info}")
                return info
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
        return {}


def main():
    """主函数：命令行接口"""
    parser = argparse.ArgumentParser(description="法律知识库一键构建脚本")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config/vector_db.yaml",
        help="配置文件路径，默认为 config/vector_db.yaml"
    )
    parser.add_argument(
        "--corpus", 
        type=str, 
        default=None,
        help="STARD语料库文件路径，默认为配置文件中的路径"
    )
    parser.add_argument(
        "--data-dir", 
        type=str, 
        default=None,
        help="JSON数据目录（备选方案）"
    )
    parser.add_argument(
        "--clear", 
        action="store_true",
        help="构建前清空集合"
    )
    parser.add_argument(
        "--info", 
        action="store_true",
        help="显示集合信息"
    )
    
    args = parser.parse_args()
    
    # 创建构建器
    builder = KnowledgeBaseBuilder(args.config)
    
    # 显示集合信息
    if args.info:
        builder.get_collection_info()
        return
    
    # 清空集合
    if args.clear:
        confirm = input("确定要清空集合吗？(y/n): ")
        if confirm.lower() == 'y':
            builder.clear_collection()
        return
    
    # 构建知识库
    try:
        if args.data_dir:
            # 从JSON文件构建（备选方案）
            builder.build_from_json_files(args.data_dir)
        else:
            # 从STARD语料库构建（主方案）
            stats = builder.build_from_stard_corpus(args.corpus)
            
            # 显示构建结果
            print("\n" + "="*50)
            print("知识库构建完成！")
            print("="*50)
            print(f"处理文档数: {stats['total_docs']}")
            print(f"生成chunks数: {stats['total_chunks']}")
            print(f"失败文档数: {stats['failed_docs']}")
            print(f"总耗时: {stats['duration']:.2f} 秒")
            print("="*50)
            
    except Exception as e:
        logger.error(f"构建过程失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()