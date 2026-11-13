#!/usr/bin/env python3
"""
向量数据库初始化脚本（统一版）
支持：
- 虚拟环境检查 + 依赖自动安装
- 内置示例法律数据生成
- 使用 LegalVectorDB 类进行嵌入和存储
- 检索测试
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional

# 设置 Hugging Face 镜像（国内加速）
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 尝试导入项目中的 LegalVectorDB
try:
    from data.vector_db import LegalVectorDB
except ImportError as e:
    print(f"❌ 无法导入 LegalVectorDB: {e}")
    print("请确保 data/vector_db.py 存在且正确")
    sys.exit(1)


# ==================== 虚拟环境 & 依赖检查 ====================
def check_virtual_env():
    """检查是否在虚拟环境中"""
    in_venv = False
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        in_venv = True
    elif sys.prefix != sys.base_prefix:
        in_venv = True
    elif os.environ.get('VIRTUAL_ENV'):
        in_venv = True

    if not in_venv:
        print("⚠️  警告: 未检测到虚拟环境！")
        print("建议使用虚拟环境避免依赖冲突:")
        print("  Windows: python -m venv venv && venv\\Scripts\\activate")
        print("  Linux/Mac: python3 -m venv venv && source venv/bin/activate")
        print()
        response = input("是否继续安装依赖到系统环境？(y/N): ")
        if response.lower() != 'y':
            print("请先创建并激活虚拟环境")
            sys.exit(1)
        return False
    else:
        print(f"✓ 虚拟环境: {sys.prefix}")
        return True


def check_and_install_dependencies():
    """检查并安装必要的依赖（chromadb, sentence-transformers, torch, pyyaml）"""
    missing_packages = []
    required = ["chromadb", "sentence_transformers", "torch", "yaml"]

    for pkg in required:
        try:
            if pkg == "yaml":
                __import__("yaml")
            else:
                __import__(pkg)
            print(f"✓ {pkg} 已安装")
        except ImportError:
            missing_packages.append(pkg)

    if missing_packages:
        print(f"\n缺少依赖库: {', '.join(missing_packages)}")
        print("\n请手动安装依赖:")
        print(f"  pip install {' '.join(missing_packages)}")
        print("\n或安装所有依赖:")
        print("  pip install -r requirements.txt")

        response = input("\n是否自动安装缺失的依赖？(y/N): ")
        if response.lower() == 'y':
            for package in missing_packages:
                print(f"\n正在安装 {package}...")
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--user", package],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    print(f"✓ {package} 安装成功")
                except subprocess.CalledProcessError as e:
                    print(f"✗ {package} 安装失败: {e.stderr}")
                    print(f"\n请手动安装: pip install {package}")
                    sys.exit(1)
        else:
            print("\n请手动安装依赖后重新运行脚本")
            sys.exit(1)


# ==================== 内置示例数据生成器 ====================
class LegalDataGenerator:
    """生成内置法律示例数据（当没有真实数据时使用）"""
    SAMPLE_DATA = {
        "民法典_相邻关系.json": {
            "law_name": "中华人民共和国民法典",
            "chapter": "物权编 第七章 相邻关系",
            "articles": [
                {"article_id": "第二百八十八条", "article_number": 288,
                 "title": "相邻关系处理原则",
                 "content": "不动产的相邻权利人应当按照有利生产、方便生活、团结互助、公平合理的原则，正确处理相邻关系。"},
                {"article_id": "第二百八十九条", "article_number": 289,
                 "title": "法律适用",
                 "content": "法律、法规对处理相邻关系有规定的，依照其规定；法律、法规没有规定的，可以按照当地习惯。"},
                {"article_id": "第二百九十条", "article_number": 290,
                 "title": "用水排水",
                 "content": "不动产权利人应当为相邻权利人用水、排水提供必要的便利。对自然流水的利用，应当在不动产的相邻权利人之间合理分配。对自然流水的排放，应当尊重自然流向。"},
                {"article_id": "第二百九十三条", "article_number": 293,
                 "title": "通风采光",
                 "content": "建造建筑物，不得违反国家有关工程建设标准，不得妨碍相邻建筑物的通风、采光和日照。"},
                {"article_id": "第二百九十四条", "article_number": 294,
                 "title": "污染物排放",
                 "content": "不动产权利人不得违反国家规定弃置固体废物，排放大气污染物、水污染物、土壤污染物、噪声、光辐射、电磁辐射等有害物质。"},
                {"article_id": "第二百九十五条", "article_number": 295,
                 "title": "挖掘土地",
                 "content": "不动产权利人挖掘土地、建造建筑物、铺设管线以及安装设备等，不得危及相邻不动产的安全。"},
                {"article_id": "第二百九十六条", "article_number": 296,
                 "title": "使用相邻不动产",
                 "content": "不动产权利人因用水、排水、通行、铺设管线等利用相邻不动产的，应当尽量避免对相邻的不动产权利人造成损害。"}
            ]
        },
        "治安管理处罚法.json": {
            "law_name": "中华人民共和国治安管理处罚法",
            "chapter": "第二节 妨害公共安全的行为",
            "articles": [
                {"article_id": "第五十八条", "article_number": 58,
                 "title": "噪声扰民",
                 "content": "违反关于社会生活噪声污染防治的法律规定，制造噪声干扰他人正常生活的，处警告；警告后不改正的，处二百元以上五百元以下罚款。"},
                {"article_id": "第七十五条", "article_number": 75,
                 "title": "饲养动物干扰他人",
                 "content": "饲养动物，干扰他人正常生活的，处警告；警告后不改正的，或者放任动物恐吓他人的，处二百元以上五百元以下罚款。驱使动物伤害他人的，依照本法第四十三条第一款的规定处罚。"}
            ]
        },
        "物业管理条例.json": {
            "law_name": "物业管理条例",
            "chapter": "第五章 物业的使用与维护",
            "articles": [
                {"article_id": "第四十五条", "article_number": 45,
                 "title": "物业服务收费",
                 "content": "物业管理区域内，供水、供电、供气、供热、通信、有线电视等单位应当向最终用户收取有关费用。物业服务企业接受委托代收前款费用的，不得向业主收取手续费等额外费用。"},
                {"article_id": "第四十六条", "article_number": 46,
                 "title": "公共区域管理",
                 "content": "对物业管理区域内违反有关治安、环保、物业装饰装修和使用等方面法律、法规规定的行为，物业服务企业应当制止，并及时向有关行政管理部门报告。"},
                {"article_id": "第五十条", "article_number": 50,
                 "title": "公共区域占用",
                 "content": "物业管理区域内按照规划建设的公共建筑和共用设施，不得改变用途。业主、物业服务企业不得擅自占用、挖掘物业管理区域内的道路、场地，损害业主的共同利益。"}
            ]
        }
    }

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def generate(self):
        """生成示例 JSON 文件"""
        print("\n📝 生成内置示例法律数据...")
        for filename, content in self.SAMPLE_DATA.items():
            filepath = self.data_dir / filename
            if filepath.exists():
                print(f"  跳过已存在: {filename}")
                continue
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
            print(f"  ✓ 生成: {filename} ({len(content['articles'])} 条条文)")
        print("✅ 示例数据生成完成")


# ==================== 主初始化类 ====================
class VectorDBInitializer:
    """使用 LegalVectorDB 统一初始化向量数据库"""

    def __init__(
        self,
        data_dir: Path,
        persist_dir: str = "./data/chroma_db",
        collection_name: str = "legal_knowledge_v1",
        embedding_model: str = "all-MiniLM-L6-v2",
        device: str = "cpu"
    ):
        self.data_dir = data_dir
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.device = device

        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def load_json_files(self) -> List[Dict]:
        """加载 data_dir 下所有 JSON 文件，转换为文档列表"""
        documents = []
        json_files = list(self.data_dir.glob("*.json"))
        if not json_files:
            print(f"⚠️ 未找到 JSON 文件，请先运行示例数据生成或放置真实数据")
            return documents

        print(f"\n📂 找到 {len(json_files)} 个 JSON 文件:")
        for json_file in json_files:
            print(f"  加载: {json_file.name}")
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                docs = self._extract_documents(data, json_file.name)
                documents.extend(docs)
                print(f"    ✓ 提取 {len(docs)} 条记录")
            except Exception as e:
                print(f"    ✗ 失败: {e}")
        return documents

    def _extract_documents(self, data: Dict, source_file: str) -> List[Dict]:
        """从 JSON 中提取文档，格式兼容 LegalVectorDB.add_documents"""
        documents = []
        if "articles" not in data:
            return documents
        law_name = data.get("law_name", source_file.replace(".json", ""))
        chapter = data.get("chapter", "")
        for article in data["articles"]:
            article_id = article.get("article_id", "")
            title = article.get("title", "")
            content = article.get("content", "")
            if not content:
                continue

            # 构建检索文本（供嵌入使用）
            text = f"{law_name} {chapter} {article_id} {title} {content}".strip()

            # 元数据（必须包含 law_name, article_no 等，用于检索后显示）
            metadata = {
                "law_name": law_name,
                "chapter": chapter,
                "article_id": article_id,
                "article_number": article.get("article_number", 0),
                "title": title,
                "source_file": source_file,
                "content_preview": content[:200] + "..." if len(content) > 200 else content
            }

            # chunk_id 使用唯一标识
            chunk_id = f"{law_name}_{article_id}".replace(" ", "_").replace("/", "_").replace("(", "").replace(")", "")
            documents.append({
                "chunk_id": chunk_id,
                "text": text,
                "metadata": metadata
            })
        return documents

    def run(self, test: bool = True) -> Dict:
        """执行初始化流程"""
        print("\n" + "█" * 60)
        print("█ 向量数据库初始化（统一版）")
        print("█ 使用 LegalVectorDB 类")
        print("█" * 60)

        start = time.time()

        # 1. 生成示例数据（如果 data_dir 为空）
        if not list(self.data_dir.glob("*.json")):
            generator = LegalDataGenerator(self.data_dir)
            generator.generate()

        # 2. 加载文档
        documents = self.load_json_files()
        if not documents:
            return {"success": False, "documents": 0, "vectors": 0}

        print(f"\n✅ 共加载 {len(documents)} 条法律记录")

        # 3. 初始化 LegalVectorDB 并插入数据
        print(f"\n🚀 初始化向量数据库 (模型: {self.embedding_model})")
        db = LegalVectorDB(
            persist_directory=str(self.persist_dir),
            collection_name=self.collection_name,
            embedding_model=self.embedding_model,
            device=self.device,
            normalize_embeddings=True,
            max_retries=3,
            timeout=30.0
        )
        print("✓ 数据库连接成功")

        # 可选：清空旧集合（如果需要重新构建）
        # db.clear_collection()

        # 批量插入
        print(f"\n📥 开始嵌入并存储 {len(documents)} 条文档...")
        result = db.add_documents(documents, batch_size=32, show_progress=True)

        elapsed = time.time() - start
        print("\n" + "=" * 60)
        print("✅ 初始化完成！")
        print("=" * 60)
        print(f"法律条文数: {len(documents)} 条")
        print(f"成功存储: {result['inserted']} 条")
        print(f"失败: {result['failed']} 条")
        print(f"耗时: {elapsed:.2f} 秒")
        print(f"集合名称: {self.collection_name}")
        print(f"存储路径: {self.persist_dir}")

        # 4. 测试检索
        if test and result['inserted'] > 0:
            self._test_search(db)

        return {"success": True, "documents": len(documents), "vectors": result['inserted']}

    def _test_search(self, db: LegalVectorDB):
        """简单检索测试"""
        queries = [
            "邻居装修噪音太大怎么办",
            "楼上漏水到我家，谁负责维修",
            "小区物业不作为，业主如何维权",
            "高空抛物造成伤害谁负责"
        ]
        print("\n" + "=" * 60)
        print("🔍 检索测试")
        print("=" * 60)
        for q in queries:
            print(f"\n查询: {q}")
            try:
                res = db.search(q, top_k=3)
                docs = res.get("documents", [[]])[0]
                metas = res.get("metadatas", [[]])[0]
                scores = res.get("scores", [[]])[0]
                for i, (doc, meta, score) in enumerate(zip(docs, metas, scores)):
                    print(f"  结果 {i+1}: {meta.get('law_name', '')} {meta.get('article_id', '')} (相似度 {score:.3f})")
            except Exception as e:
                print(f"  检索失败: {e}")


# ==================== 命令行入口 ====================
def main():
    parser = argparse.ArgumentParser(description="初始化向量数据库（统一版）")
    parser.add_argument("--data-dir", type=str, default="./data/raw", help="法律条文 JSON 数据目录")
    parser.add_argument("--persist-dir", type=str, default="./data/chroma_db", help="向量数据库持久化目录")
    parser.add_argument("--collection-name", type=str, default="legal_knowledge_v1", help="集合名称")
    parser.add_argument("--embedding-model", type=str, default="all-MiniLM-L6-v2", help="嵌入模型名称")
    parser.add_argument("--device", type=str, default="cpu", help="设备 (cpu/cuda)")
    parser.add_argument("--no-test", action="store_true", help="不运行检索测试")
    args = parser.parse_args()

    # 检查虚拟环境和依赖
    check_virtual_env()
    check_and_install_dependencies()

    # 将相对路径转为项目根目录下的绝对路径
    data_dir = project_root / args.data_dir
    persist_dir = args.persist_dir  # LegalVectorDB 内部会基于项目根目录处理相对路径

    initializer = VectorDBInitializer(
        data_dir=data_dir,
        persist_dir=persist_dir,
        collection_name=args.collection_name,
        embedding_model=args.embedding_model,
        device=args.device
    )
    result = initializer.run(test=not args.no_test)
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()