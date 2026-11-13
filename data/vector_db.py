"""Production-grade legal vector database based on ChromaDB and sentence-transformers."""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import jieba
import numpy as np

# 尝试导入结构化日志库（可选依赖）
try:
    import structlog
except ImportError:  # pragma: no cover - optional dependency
    structlog = None

# 创建日志记录器
LOGGER = (
    structlog.get_logger("legal_vector_db")
    if structlog
    else logging.getLogger("legal_vector_db")
)


class LegalVectorDBError(RuntimeError):
    """法律向量数据库的基类异常"""


class ModelInitializationError(LegalVectorDBError):
    """当sentence-transformer模型初始化失败时抛出"""


class DataValidationError(LegalVectorDBError):
    """当数据块格式无效时抛出"""


class LegalVectorDB:
    """面向法律检索的生产就绪向量数据库封装类

    Example:
        >>> vectordb = LegalVectorDB()
        >>> stats = vectordb.add_documents([{
        ...     "chunk_id": "law18chunk1",
        ...     "text": "成年人为完全民事行为能力人。",
        ...     "metadata": {"law_name": "民法典", "article_no": "18"}
        ... }])
        >>> results = vectordb.search("民事行为能力")
        >>> vectordb.close()
    """
 # 备用模型列表，如果默认模型不可用，会尝试这些模型
    FALLBACK_MODELS: Tuple[str, ...] = (
        "BAAI/bge-m3",
        "BAAI/bge-large-zh-v1.5",
        "shibing624/text2vec-base-chinese",
    )

    def __init__(
        self,
        persist_directory: str = "./data/chroma_db",
        collection_name: str = "legal_knowledge",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        device: str = "cpu",
        normalize_embeddings: bool = True,
        **kwargs: Any,
    ) -> None:
        self._lock = threading.RLock()
        self.client = None
        self.collection = None
        self.model = None
        self.model_name = embedding_model
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.model_cache_directory = Path(kwargs.pop("model_cache_directory", "./data/model_cache"))
        self.backup_directory = Path(kwargs.pop("backup_directory", "./data/backups"))
        self.max_retries = int(kwargs.pop("max_retries", 3))
        self.timeout = float(kwargs.pop("timeout", 30.0))
        self.last_backup_time: Optional[str] = None
        self.vector_db_version = "1.0.0"
        self._client_factory: Optional[Callable[..., Any]] = kwargs.pop("client_factory", None)
        self._model_loader: Optional[Callable[..., Any]] = kwargs.pop("model_loader", None)
        self._collection_kwargs = kwargs
        self._ensure_logger()
        self.init(
            persist_directory=persist_directory,
            collection_name=collection_name,
            embedding_model=embedding_model,
            device=device,
            normalize_embeddings=normalize_embeddings,
            **kwargs,
        )

    def init(
        self,
        persist_directory: str = "./data/chroma_db",
        collection_name: str = "legal_knowledge",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
        device: str = "cpu",
        normalize_embeddings: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize vector store and embedding model.

        Args:
            persist_directory: Chroma persistence folder.
            collection_name: Chroma collection name.
            embedding_model: Sentence-transformers model id or local path.
            device: "cpu" or "cuda".
            normalize_embeddings: Whether to L2-normalize embeddings.
            **kwargs: Extra collection/client settings.
        """
        with self._lock:
            self.persist_directory = Path(persist_directory)
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self.model_cache_directory.mkdir(parents=True, exist_ok=True)
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            self.collection_name = collection_name
            self.model_name = embedding_model
            self.device = device
            self.normalize_embeddings = normalize_embeddings

            self.client = self._create_client(str(self.persist_directory), **kwargs)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "domain": "legal",
                    "distance_metric": "cosine",
                    "vector_db_version": self.vector_db_version,
                },
            )
            self.model = self._load_embedding_model(self.model_name, self.device)
            self._validate_model_support_chinese(self.model)
            self._warm_up_model(self.model)
            self._log_info("vectordb initialized", collection=self.collection_name, model=self.model_name)

    def add_documents(
        self,
        chunks: List[Dict[str, Any]],
        batch_size: int = 100,
        upsert: bool = False,
        show_progress: bool = True,
    ) -> Dict[str, Any]:
        """批量插入文档块到向量数据库"""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not chunks:
            return {"requested": 0, "inserted": 0, "failed": 0, "skipped": 0, "elapsed": 0.0, "throughput": 0.0}

        started = time.perf_counter()
        inserted = 0
        skipped = 0
        failed = 0
        errors: List[str] = []
        total = len(chunks)

        # 1. 去重
        deduped = self._deduplicate_input(chunks)
        skipped += total - len(deduped)
        # 2. 分批处理
        iterator = range(0, len(deduped), batch_size)

        for offset in iterator:
            batch = deduped[offset : offset + batch_size]
            try:
                ids, docs, metas = self._prepare_batch(batch)
            except DataValidationError as exc:
                failed += len(batch)
                errors.append(str(exc))
                continue
            
            # 3. 生成嵌入向量
            embeddings = self._encode_documents(docs)
            try:
                # 4. 写入数据库
                self._write_batch(ids=ids, docs=docs, metas=metas, embeds=embeddings, upsert=upsert)
                inserted += len(ids)
            except Exception as exc:  # pragma: no cover - depends on backend behavior
                failed += len(ids)
                errors.append(str(exc))
                self._log_error("batch insert failed", error=str(exc), batch_size=len(ids))
            finally:
                self._cleanup_memory()
            # 5. 显示进度
            if show_progress:
                self._log_info("add progress", processed=min(offset + batch_size, len(deduped)), total=len(deduped))
        # 6. 计算统计信息
        elapsed = max(time.perf_counter() - started, 1e-9)
        return {
            "requested": total,
            "inserted": inserted,
            "failed": failed,
            "skipped": skipped,
            "elapsed": elapsed,
            "throughput": inserted / elapsed,
            "errors": errors[:10],
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
        include: List[str] = None,
    ) -> Dict[str, Any]:
        """带可选元数据和内容过滤的语义检索"""
        if include is None:
            include = ["documents", "metadatas", "distances"]
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not query or not query.strip():
            raise ValueError("query must not be empty")

        started = time.perf_counter()
        # 1. 将查询文本转换为向量
        query_vector = self._encode_documents([query])[0]

        with self._lock:
            # 2. 在集合中查询相似向量
            result = self.collection.query(
                query_embeddings=[query_vector.tolist()],
                n_results=top_k,
                where=where,
                where_document=where_document,
                include=include,
            )

        # 3. 处理距离和分数
        distances = result.get("distances", [[]])
        scores = [[float(max(0.0, 1.0 - d)) for d in row] for row in distances]
        # 4. 根据阈值过滤结果
        if score_threshold > 0.0:
            result = self._filter_by_threshold(result, scores, score_threshold)
            distances = result.get("distances", [[]])
            scores = [[float(max(0.0, 1.0 - d)) for d in row] for row in distances]
        # 5. 添加额外信息到结果
        result["scores"] = scores
        result["query_time"] = time.perf_counter() - started
        return result

    def search_with_metadata(
            self,
            query: str,
            top_k: int = 5,
            where: Optional[Dict[str, Any]] = None,
            score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        增强版搜索，返回带元数据和分数的列表，兼容队友的检索接口。
        """
        raw = self.search(query, top_k=top_k, where=where)
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]
        scores = [1.0 - d for d in dists] if dists else []
        results = []
        for i, doc in enumerate(docs):
            results.append({
                "text": doc,
                "metadata": metas[i] if i < len(metas) else {},
                "score": scores[i] if i < len(scores) else 0.0,
                "distance": dists[i] if i < len(dists) else 1.0,
            })
        if score_threshold > 0:
            results = [r for r in results if r["score"] >= score_threshold]
        return results[:top_k]
    async def asearch(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """异步搜索，适用于高并发API服务器"""
        return await asyncio.to_thread(self.search, *args, **kwargs)

    def update_document(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        """通过文档块ID进行幂等性更新插入（存在则更新，不存在则插入）"""
        return self.add_documents([chunk], batch_size=1, upsert=True, show_progress=False)

    def delete_by_ids(self, ids: Sequence[str]) -> Dict[str, Any]:
        """通过ID删除文档"""
        id_list = [i for i in ids if i]
        if not id_list:
            return {"deleted": 0}
        with self._lock:
            self.collection.delete(ids=id_list)
        return {"deleted": len(id_list)}

    def get_collection_stats(self) -> Dict[str, Any]:
        """返回集合和存储统计信息"""
        count = self._get_total_chunks()
        return {
            "collection_name": self.collection_name,
            "document_count": count,
            "embedding_model": self.model_name,
            "persist_directory": str(self.persist_directory),
            "storage_bytes": self._get_storage_usage(),
            "version": self.vector_db_version,
        }

    def backup(self, target_path: Optional[str] = None) -> str:
        """备份持久化向量数据目录"""
        target = Path(target_path) if target_path else self.backup_directory / datetime.now().strftime("%Y%m%d_%H%M%S")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(f"backup target already exists: {target}")
        with self._lock:
            shutil.copytree(self.persist_directory, target)
        self.last_backup_time = datetime.now().isoformat()
        self._log_info("backup completed", target=str(target))
        return str(target)

    def health_check(self) -> Dict[str, Any]:
        """返回健康检查状态，用于监控端点"""
        stats = self.get_collection_stats()
        return {
            "status": "healthy",
            "collection_size": stats["document_count"],
            "embedding_model": self.model_name,
            "chunk_count": self._get_total_chunks(),
            "last_backup": self.last_backup_time,
            "storage_size": stats["storage_bytes"],
            "device": self.device,
            "fallback_models": list(self.FALLBACK_MODELS),
        }

    def close(self) -> None:
        """释放运行时资源"""
        with self._lock:
            self.collection = None
            self.client = None
            self.model = None
        self._cleanup_memory()
        self._log_info("vectordb closed")

    def rag_query_engine(
        self,
        query: str,
        top_k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.0,
        include: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """RAG 查询引擎：封装完整的检索流程
        
        接收用户查询，执行向量检索，返回带元数据和相似度分数的结果列表。
        
        Args:
            query: 用户查询文本
            top_k: 返回的最相似结果数量
            where: 元数据过滤条件，例如 {"law_name": "民法典"}
            where_document: 文档内容过滤条件，例如 {"$contains": "民事行为能力"}
            score_threshold: 相似度分数阈值，取值范围 0.0-1.0
            include: 指定返回的字段，默认为 ["documents", "metadatas", "distances"]
            
        Returns:
            List[Dict[str, Any]]: 包含检索结果的字典列表，每个字典包含：
                - text: 文档内容
                - metadata: 文档元数据
                - score: 相似度分数
                - distance: 余弦距离
                
        Raises:
            ValueError: 参数无效时抛出
            LegalVectorDBError: 检索过程发生错误时抛出
        """
        if include is None:
            include = ["documents", "metadatas", "distances"]
        
        if not query or not query.strip():
            raise ValueError("查询文本不能为空")
        
        if top_k <= 0:
            raise ValueError("top_k 必须为正整数")
        
        if not 0.0 <= score_threshold <= 1.0:
            raise ValueError("score_threshold 必须在 0.0 到 1.0 之间")
        
        try:
            # 执行向量检索
            search_result = self.search(
                query=query,
                top_k=top_k,
                where=where,
                where_document=where_document,
                score_threshold=score_threshold,
                include=include
            )
            
            # 构建标准化的结果列表
            results: List[Dict[str, Any]] = []
            
            # 提取检索结果
            documents = search_result.get("documents", [[]])
            metadatas = search_result.get("metadatas", [[]])
            distances = search_result.get("distances", [[]])
            scores = search_result.get("scores", [[]])
            
            # 确保所有列表长度一致
            if not documents[0]:
                return results
            
            for i in range(len(documents[0])):
                result_item = {
                    "text": documents[0][i] if i < len(documents[0]) else "",
                    "metadata": metadatas[0][i] if i < len(metadatas[0]) else {},
                    "distance": distances[0][i] if i < len(distances[0]) else 1.0,
                    "score": scores[0][i] if i < len(scores[0]) else 0.0
                }
                results.append(result_item)
            
            # 按分数降序排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            # 添加查询统计信息
            if results:
                results[0]["_query_stats"] = {
                    "query_time": search_result.get("query_time", 0.0),
                    "total_results": len(results),
                    "original_query": query
                }
            
            return results
            
        except Exception as e:
            error_msg = f"RAG查询失败: {str(e)}"
            self._log_error("rag_query_engine failed", error=error_msg, query=query)
            raise LegalVectorDBError(error_msg) from e
    
# ============ 私有方法 ============
    def _create_client(self, persist_directory: str, **kwargs: Any) -> Any:
        """创建ChromaDB客户端"""
        if self._client_factory is not None:
            return self._client_factory(persist_directory=persist_directory, **kwargs)
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise LegalVectorDBError("chromadb is not installed, please pip install chromadb>=0.4.0") from exc
        return chromadb.PersistentClient(path=persist_directory)

    def _load_embedding_model(self, model_name: str, device: str) -> Any:
        """加载嵌入模型"""
        if self._model_loader is not None:
            return self._model_loader(model_name=model_name, device=device, cache_folder=str(self.model_cache_directory))
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - runtime dependency
            raise ModelInitializationError(
                "sentence-transformers is not installed, please pip install sentence-transformers"
            ) from exc
        try:
            return SentenceTransformer(model_name, device=device, cache_folder=str(self.model_cache_directory))
        except Exception as exc:  # pragma: no cover - runtime dependency
            self._log_error("embedding model load failed", model=model_name, error=str(exc))
            raise ModelInitializationError(
                "模型下载失败。请检查网络连接，或先手动下载模型到本地后传入本地路径。"
            ) from exc

    def _validate_model_support_chinese(self, model: Any) -> None:
        """验证模型是否支持中文"""
        probe = model.encode(["法律条文测试"], show_progress_bar=False)
        if probe is None or len(probe) == 0:
            raise ModelInitializationError("embedding model validation failed")

    def _warm_up_model(self, model: Any) -> None:
        """预热模型"""
        model.encode(["法律向量模型预热"], show_progress_bar=False)

    def _prepare_batch(self, chunks: Sequence[Dict[str, Any]]) -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
        """准备批次数据，返回(IDs, 文档, 元数据)三元组"""
        ids: List[str] = []
        docs: List[str] = []
        metas: List[Dict[str, Any]] = []
        for chunk in chunks:
            self._validate_chunk_payload(chunk)
            ids.append(str(chunk["chunk_id"]))
            docs.append(str(chunk["text"]))
            metas.append(self._sanitize_metadata(chunk["metadata"]))
        return ids, docs, metas

    def _write_batch(
        self,
        ids: List[str],
        docs: List[str],
        metas: List[Dict[str, Any]],
        embeds: np.ndarray,
        upsert: bool,
    ) -> None:
        """写入批次数据到数据库，带重试机制"""
        for attempt in range(1, self.max_retries + 1):
            try:
                with self._lock:
                    if upsert:
                        self.collection.upsert(
                            ids=ids,
                            documents=docs,
                            metadatas=metas,
                            embeddings=embeds.tolist(),
                        )
                    else:
                        self.collection.add(
                            ids=ids,
                            documents=docs,
                            metadatas=metas,
                            embeddings=embeds.tolist(),
                        )
                return
            except Exception as exc:
                if attempt >= self.max_retries:
                    raise
                self._log_error("write retry", attempt=attempt, error=str(exc))
                time.sleep(0.1 * attempt)

    def _encode_documents(self, docs: Sequence[str]) -> np.ndarray:
        """将文档编码为向量"""
        vectors = self.model.encode(
            list(docs),
            batch_size=min(128, max(1, len(docs))),
            show_progress_bar=False,
            normalize_embeddings=self.normalize_embeddings,
        )
        arr = np.asarray(vectors, dtype=np.float32)
        if self.normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
            arr = arr / norms
        return arr

    def _filter_by_threshold(
        self,
        result: Dict[str, Any],
        scores: List[List[float]],
        score_threshold: float,
    ) -> Dict[str, Any]:
        """根据分数阈值过滤结果"""
        filtered: Dict[str, Any] = {k: [[]] for k in result.keys()}
        for idx, score in enumerate(scores[0]):
            if score < score_threshold:
                continue
            for key in result.keys():
                if result.get(key):
                    filtered[key][0].append(result[key][0][idx])
        return filtered

    def _deduplicate_input(self, chunks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对输入数据进行去重"""
        seen = set()
        deduped: List[Dict[str, Any]] = []
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            if not chunk_id or chunk_id in seen:
                continue
            seen.add(chunk_id)
            deduped.append(chunk)
        return deduped

    @staticmethod
    def _validate_chunk_payload(chunk: Dict[str, Any]) -> None:
        """验证数据块格式"""
        if not isinstance(chunk, dict):
            raise DataValidationError("chunk must be dict")
        for key in ("chunk_id", "text", "metadata"):
            if key not in chunk:
                raise DataValidationError(f"chunk missing field: {key}")
        if not str(chunk["text"]).strip():
            raise DataValidationError("chunk text must not be empty")
        if not isinstance(chunk["metadata"], dict):
            raise DataValidationError("metadata must be dict")

    @staticmethod
    def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
        """清理元数据，确保可以序列化"""
        clean: Dict[str, Any] = {}
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                clean[str(key)] = value
            elif value is None:
                clean[str(key)] = ""
            else:
                clean[str(key)] = str(value)
        return clean

    def _get_total_chunks(self) -> int:
        """获取文档块总数"""
        with self._lock:
            return int(self.collection.count())

    def _get_storage_usage(self) -> int:
        """获取存储使用量（字节）"""
        total = 0
        if not self.persist_directory.exists():
            return total
        for root, _, files in os.walk(self.persist_directory):
            for file in files:
                try:
                    total += (Path(root) / file).stat().st_size
                except OSError:
                    continue
        return total

    @staticmethod
    def _cleanup_memory() -> None:
        gc.collect()

    @staticmethod
    def _ensure_logger() -> None:
        """确保日志记录器已配置"""
        if structlog:
            return
        if LOGGER.handlers:
            return
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    @staticmethod
    def _log_info(message: str, **kwargs: Any) -> None:
        if structlog:
            LOGGER.info(message, **kwargs)
        else:
            LOGGER.info("%s | %s", message, kwargs)

    @staticmethod
    def _log_error(message: str, **kwargs: Any) -> None:
        if structlog:
            LOGGER.error(message, **kwargs)
        else:
            LOGGER.error("%s | %s", message, kwargs)

# ========== 适配器：为 master 分支的 knowledge_repository 提供兼容接口 ==========

class SearchHit:
    """统一检索命中结果（仓储层契约）。

    修复 P1：仓储层读取 payload / matched_tokens / score，
    此前适配器仅有 text/metadata/score，导致双库检索 AttributeError。
    保留 text/metadata 以兼容旧调用方。
    """

    def __init__(self, text: str = "", metadata: dict | None = None, score: float = 0.0,
                 payload: dict | None = None, matched_tokens: list | None = None):
        self.text = text
        self.metadata = metadata or {}
        self.score = score
        # payload 为原始文档字典；缺省回退到 metadata
        self.payload = payload if payload is not None else self.metadata
        self.matched_tokens = matched_tokens or []


class ChromaVectorStore:
    """基于 LegalVectorDB 的 Chroma 检索适配器（懒加载）。

    修复 P1/P2：
    - search 签名对齐仓储契约 (query, dispute_type, region, limit)，返回带 payload/matched_tokens 的 SearchHit；
    - 新增 count()/is_available()，供运行状态探测使用；
    - 路径统一取 settings.CHROMA_DIR，消除硬编码 "./storage/chroma"；
    - 仅在真正检索/写入时才初始化 embedding 模型，local_json 默认路径不触发模型下载。
    """

    def __init__(self, collection_name: str, embedder=None):
        from api import settings
        self.collection_name = collection_name
        # 兼容 ingestion 传入 embedder；底层编码仍由 LegalVectorDB 负责
        self._embedder = embedder
        self._persist_directory = str(settings.CHROMA_DIR)
        self._db = None  # 懒加载 LegalVectorDB

    def _ensure_db(self) -> "LegalVectorDB":
        if self._db is None:
            from api import settings
            self._db = LegalVectorDB(
                persist_directory=self._persist_directory,
                collection_name=self.collection_name,
                embedding_model=settings.EMBEDDING_MODEL,
                device=settings.EMBEDDING_DEVICE,
            )
        return self._db

    def _client(self):
        import chromadb
        return chromadb.PersistentClient(path=self._persist_directory)

    def count(self) -> int:
        """返回 collection 文档数（不加载 embedding 模型）。"""
        try:
            collection = self._client().get_collection(self.collection_name)
            return int(collection.count())
        except Exception:
            return 0

    def is_available(self) -> bool:
        """collection 是否存在（不加载 embedding 模型）。"""
        try:
            self._client().get_collection(self.collection_name)
            return True
        except Exception:
            return False

    def search(self, query: str, *, dispute_type: str | None = None,
               region: str | None = None, limit: int = 5) -> list:
        """语义检索，返回 SearchHit 列表（payload=metadata，matched_tokens 为空）。"""
        if not query or not query.strip():
            return []
        where = {}
        if dispute_type:
            where["dispute_type"] = dispute_type
        if region:
            where["region"] = {"$in": ["全国", region]}
        if len(where) > 1:
            where = {"$and": [{key: value} for key, value in where.items()]}
        results = self._ensure_db().search_with_metadata(query, top_k=limit, where=where or None)
        hits = []
        for r in results:
            metadata = r.get("metadata", {})
            hits.append(SearchHit(
                text=r.get("text", ""),
                metadata=metadata,
                score=r.get("score", 0.0),
                payload=metadata,
                matched_tokens=[],
            ))
        return hits

    def add_documents(self, documents: list) -> int:
        """添加文档（格式 [{"id","document","metadata"}]），返回插入数量。"""
        chunks = []
        for doc in documents:
            chunk_id = doc.get("id")
            text = doc.get("document", "")
            metadata = doc.get("metadata", {})
            if chunk_id and text:
                chunks.append({"chunk_id": chunk_id, "text": text, "metadata": metadata})
        if not chunks:
            return 0
        result = self._ensure_db().add_documents(chunks)
        return result.get("inserted", 0)

    def clear(self):
        """清空 collection（重建用）。"""
        import chromadb
        client = chromadb.PersistentClient(path=self._persist_directory)
        try:
            client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._db = None


class LocalVectorStore:
    """本地 JSON 关键词检索（离线回退）。

    修复 P1：构造接受“数据列表 + 文本字段”，与仓储层调用一致；
    search 支持 dispute_type/region 过滤，返回带 payload/matched_tokens 的 SearchHit。
    地域过滤将“全国”视为匹配任意地域（全国性法规普遍适用）。
    """

    def __init__(self, items, *, text_fields: list | None = None, keyword_field: str = "keywords"):
        # 兼容传入文件路径的旧用法
        if isinstance(items, (str, Path)):
            import json
            path = Path(items)
            items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        self.data = list(items or [])
        self.text_fields = text_fields or ["title", "content", "excerpt", "summary"]
        self.keyword_field = keyword_field

    def _item_text(self, item: dict) -> str:
        parts = [str(item.get(f, "") or "") for f in self.text_fields]
        keywords = item.get(self.keyword_field) or []
        if isinstance(keywords, list):
            parts.extend(str(k) for k in keywords)
        return " ".join(parts)

    def search(self, query: str, *, dispute_type: str | None = None,
               region: str | None = None, limit: int = 5) -> list:
        """关键词重叠打分检索；空查询/空库返回空列表（边缘覆盖）。"""
        if not query or not query.strip() or not self.data:
            return []
        query_tokens = set(jieba.lcut_for_search(query))
        scored = []
        for item in self.data:
            if dispute_type and item.get("dispute_type") not in (None, dispute_type):
                continue
            if region:
                item_region = item.get("region")
                if item_region not in (None, "全国", region):
                    continue
            item_tokens = set(jieba.lcut_for_search(self._item_text(item)))
            matched = query_tokens & item_tokens
            if not matched:
                continue
            score = len(matched) / max(len(query_tokens), 1)
            scored.append((score, sorted(matched), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, matched, item in scored[:limit]:
            hits.append(SearchHit(
                text=self._item_text(item),
                metadata=item,
                score=round(score, 4),
                payload=item,
                matched_tokens=matched,
            ))
        return hits

# ========== build_embedder 函数（供 ingestion 使用） ==========
def build_embedder():
    """构建嵌入器，返回一个可调用对象，用于将文本转为向量"""
    from sentence_transformers import SentenceTransformer
    model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    device = os.getenv("EMBEDDING_DEVICE", "cpu")
    model = SentenceTransformer(model_name, device=device)
    def embedder(texts):
        # texts 可以是字符串列表
        return model.encode(texts, normalize_embeddings=True)
    return embedder