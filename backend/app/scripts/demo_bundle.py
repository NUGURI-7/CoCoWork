"""演示场景数据的导出 / 导入：把一套配好的场景从一个环境搬到另一个环境。

一个场景依赖的东西：业务 Agent、工作空间（含 supervisor 设置与成员）、成员挂的知识库
（连文档原件）、所有这些用到的模型。导出时按名字记引用，导入时在目标环境的管理员名下
按名字「有则更新、无则新建」，所以可以重复执行；编号由目标环境重新生成。

    # 源环境：导出到目录（scene=类型:编号，可多个）
    uv run python -m app.scripts.demo_bundle export <out_dir> \\
        --scene store-audio=agent:<agent_id> \\
        --scene doc-workspace=workspace:<workspace_id>

    # 目标环境：导入（模型密钥从 stdin 读，不落盘）
    python -m app.scripts.demo_bundle import <bundle_dir> < secrets.json

导入结束打印 DEMO_SCENES 的 JSON，填进目标环境 .env。

密钥单独成文件 secrets.json：源环境用自己的 ENCRYPTION_KEY 解密，目标环境用自己的重新加密，
密文不跨环境搬。bundle.json 与文档原件不含任何密钥。
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.storage import storage
from app.db.postgresql import pg_client
from app.models import Agent, KnowledgeBase, User, Workspace, WorkspaceMember
from app.models.knowledge import Document, DocStatus
from app.models.model.ai_model import AIModel
from app.models.model.provider_model import Provider
from app.schemas.knowledge.knowledge_base_schema import KnowledgeBaseCreate
from app.schemas.model.ai_model_schema import ModelCreate
from app.services.knowledge.document_service import DocumentService
from app.services.knowledge.knowledge_base_service import KnowledgeBaseService
from app.services.model.ai_model_service import AIModelService
from app.services.model.credentials import dump_credentials, load_credentials

logger = logging.getLogger(__name__)

BUNDLE_FILE = "bundle.json"
SECRETS_FILE = "secrets.json"
DOCS_DIR = "docs"
_PARSE_TIMEOUT_S = 600


# ==================== 导出 ====================

def _model_key(model: AIModel) -> str:
    return f"{model.provider.provider_type}:{model.provider.name}:{model.model_name}:{model.model_type}"


class _Exporter:
    def __init__(self, out: Path) -> None:
        self.out = out
        self.providers: dict[str, dict[str, Any]] = {}
        self.secrets: dict[str, dict[str, Any]] = {}
        self.models: dict[str, dict[str, Any]] = {}
        self.kbs: dict[str, dict[str, Any]] = {}
        self.agents: dict[str, dict[str, Any]] = {}
        self.workspaces: dict[str, dict[str, Any]] = {}

    async def model_ref(self, model_id: str | UUID | None) -> str | None:
        if not model_id:
            return None
        model = await AIModel.get(id=model_id).select_related("provider")
        key = _model_key(model)
        if key not in self.models:
            provider = model.provider
            pkey = f"{provider.provider_type}:{provider.name}"
            if pkey not in self.providers:
                self.providers[pkey] = {
                    "name": provider.name,
                    "provider_type": provider.provider_type,
                    "base_url": provider.base_url,
                    "description": provider.description,
                }
                self.secrets[pkey] = load_credentials(
                    provider.provider_type, provider.credentials_encrypted,
                ).model_dump()
            self.models[key] = {
                "provider": pkey,
                "model_name": model.model_name,
                "display_name": model.display_name,
                "model_type": model.model_type,
                "config": model.config,
                "base_url": model.base_url,
                "credentials": (
                    load_credentials(provider.provider_type, model.credentials_encrypted).model_dump()
                    if model.credentials_encrypted else None
                ),
            }
        return key

    async def kb_ref(self, kb_id: str) -> str:
        kb = await KnowledgeBase.get(id=kb_id)
        if kb.name not in self.kbs:
            docs = await Document.filter(knowledge_base_id=kb.id).order_by("name")
            kb_dir = self.out / DOCS_DIR / str(len(self.kbs))
            kb_dir.mkdir(parents=True, exist_ok=True)
            files = []
            for doc in docs:
                (kb_dir / doc.name).write_bytes(await storage.read(doc.storage_key))
                files.append(doc.name)
            self.kbs[kb.name] = {
                "name": kb.name,
                "description": kb.description,
                "retrieval_mode": kb.retrieval_mode,
                "parse_backend": kb.parse_backend,
                "chunk_config": kb.chunk_config,
                "embedding_model": await self.model_ref(kb.embedding_model_id),
                "rerank_model": await self.model_ref(kb.rerank_model_id),
                "dir": str(kb_dir.relative_to(self.out)),
                "files": files,
            }
        return kb.name

    async def portable_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """把配置里按编号引用的模型 / 知识库换成按名字引用。"""
        cfg = json.loads(json.dumps(config))
        for slot in (cfg.get("models") or {}).values():
            if isinstance(slot, dict) and slot.get("id"):
                slot["id"] = await self.model_ref(slot["id"])
        cfg["knowledge"] = [await self.kb_ref(k) for k in cfg.get("knowledge") or []]
        if cfg.get("mcp_servers") or cfg.get("skills"):
            raise SystemExit("暂不支持导出挂了 MCP 服务或上传 skill 的 Agent")
        return cfg

    async def agent_ref(self, agent: Agent) -> str:
        if agent.name not in self.agents:
            self.agents[agent.name] = {
                "name": agent.name,
                "description": agent.description,
                "template": agent.template,
                "config": await self.portable_config(agent.config),
            }
        return agent.name

    async def workspace_ref(self, ws: Workspace) -> str:
        members = await WorkspaceMember.filter(workspace_id=ws.id).prefetch_related("agent")
        self.workspaces[ws.name] = {
            "name": ws.name,
            "description": ws.description,
            "avatar_url": ws.avatar_url,
            "supervisor": await self.portable_config(ws.supervisor or {}),
            "config": ws.config,
            "members": [
                {"agent": await self.agent_ref(m.agent), "config": m.config} for m in members
            ],
        }
        return ws.name

    async def run(self, scenes: dict[str, tuple[str, str]]) -> None:
        exported: dict[str, dict[str, str]] = {}
        for scene, (kind, target_id) in scenes.items():
            if kind == "agent":
                ref = await self.agent_ref(await Agent.get(id=target_id))
            elif kind == "workspace":
                ref = await self.workspace_ref(await Workspace.get(id=target_id))
            else:
                raise SystemExit(f"场景类型只能是 agent / workspace：{kind}")
            exported[scene] = {"kind": kind, "name": ref}

        bundle = {
            "scenes": exported,
            "providers": list(self.providers.values()),
            "models": self.models,
            "knowledge_bases": list(self.kbs.values()),
            "agents": list(self.agents.values()),
            "workspaces": list(self.workspaces.values()),
        }
        (self.out / BUNDLE_FILE).write_text(json.dumps(bundle, ensure_ascii=False, indent=2))
        (self.out / SECRETS_FILE).write_text(json.dumps(self.secrets, ensure_ascii=False))
        (self.out / SECRETS_FILE).chmod(0o600)
        logger.info(
            "导出完成：%d 个模型、%d 个知识库、%d 个 Agent、%d 个工作空间 → %s",
            len(self.models), len(self.kbs), len(self.agents), len(self.workspaces), self.out,
        )


# ==================== 导入 ====================

class _Importer:
    def __init__(self, root: Path, bundle: dict[str, Any], secrets: dict[str, Any], admin: User) -> None:
        self.root = root
        self.bundle = bundle
        self.secrets = secrets
        self.admin = admin
        self.model_ids: dict[str, str] = {}
        self.kb_ids: dict[str, str] = {}
        self.agent_ids: dict[str, UUID] = {}

    async def providers(self) -> dict[str, Provider]:
        result = {}
        for p in self.bundle["providers"]:
            key = f"{p['provider_type']}:{p['name']}"
            ciphertext = dump_credentials(p["provider_type"], self.secrets[key])
            provider = await Provider.filter(
                created_by=self.admin, provider_type=p["provider_type"], name=p["name"],
            ).first()
            if provider is None:
                provider = await Provider.create(
                    created_by=self.admin, name=p["name"], provider_type=p["provider_type"],
                    base_url=p["base_url"], credentials_encrypted=ciphertext,
                    description=p["description"],
                )
            else:
                provider.base_url = p["base_url"]
                provider.credentials_encrypted = ciphertext
                await provider.save(update_fields=["base_url", "credentials_encrypted", "updated_at"])
            result[key] = provider
            logger.info("供应商就绪：%s", key)
        return result

    async def models(self, providers: dict[str, Provider]) -> None:
        service = AIModelService()
        for key, m in self.bundle["models"].items():
            provider = providers[m["provider"]]
            model = await AIModel.filter(
                provider=provider, model_name=m["model_name"], model_type=m["model_type"],
            ).first()
            if model is None:
                model = await service.create(self.admin, provider.id, ModelCreate(
                    model_name=m["model_name"], display_name=m["display_name"],
                    model_type=m["model_type"], config=m["config"], base_url=m["base_url"],
                    credentials=m["credentials"] or {},
                ))
            self.model_ids[key] = str(model.id)
            logger.info("模型就绪：%s", key)

    async def knowledge_bases(self) -> None:
        kb_service, doc_service = KnowledgeBaseService(), DocumentService()
        for k in self.bundle["knowledge_bases"]:
            kb = await KnowledgeBase.filter(created_by=self.admin, name=k["name"]).first()
            if kb is None:
                out = await kb_service.create(self.admin, KnowledgeBaseCreate(
                    name=k["name"], description=k["description"],
                    embedding_model_id=self.model_ids.get(k["embedding_model"] or ""),
                    retrieval_mode=k["retrieval_mode"], chunk_config=k["chunk_config"],
                    parse_backend=k["parse_backend"],
                ))
                kb = await KnowledgeBase.get(id=out.id)
            self.kb_ids[k["name"]] = str(kb.id)

            existing = set(await Document.filter(knowledge_base=kb).values_list("name", flat=True))
            pending = []
            for name in k["files"]:
                if name in existing:
                    continue
                data = (self.root / k["dir"] / name).read_bytes()
                doc = await doc_service.create_pending(self.admin, kb.id, name, len(data))
                await storage.save(doc.storage_key, io.BytesIO(data))
                await doc_service.mark_uploaded(self.admin, kb.id, doc.id)
                pending.append(doc.id)
            await self._wait_parsed(kb, pending)
            logger.info("知识库就绪：%s（新增 %d 篇）", k["name"], len(pending))

    @staticmethod
    async def _wait_parsed(kb: KnowledgeBase, doc_ids: list[UUID]) -> None:
        """等 worker 解析完；纯关键词库解析完即可检索，向量库停在 parsed 由管理员手动向量化。"""
        done = {DocStatus.PARSED, DocStatus.COMPLETED}
        for _ in range(_PARSE_TIMEOUT_S // 2):
            docs = await Document.filter(id__in=doc_ids)
            failed = [d.name for d in docs if d.status == DocStatus.FAILED]
            if failed:
                raise SystemExit(f"{kb.name} 有文档解析失败：{failed}")
            if all(d.status in done for d in docs):
                return
            await asyncio.sleep(2)
        raise SystemExit(f"{kb.name} 文档解析超时，检查 worker 是否在运行")

    def local_config(self, config: dict[str, Any]) -> dict[str, Any]:
        cfg = json.loads(json.dumps(config))
        for slot in (cfg.get("models") or {}).values():
            if isinstance(slot, dict) and slot.get("id"):
                slot["id"] = self.model_ids[slot["id"]]
        cfg["knowledge"] = [self.kb_ids[name] for name in cfg.get("knowledge") or []]
        return cfg

    async def agents(self) -> None:
        for a in self.bundle["agents"]:
            config = self.local_config(a["config"])
            agent = await Agent.filter(created_by=self.admin, name=a["name"]).first()
            if agent is None:
                agent = await Agent.create(
                    created_by=self.admin, name=a["name"], description=a["description"],
                    template=a["template"], config=config,
                )
            else:
                if agent.template != a["template"]:
                    raise SystemExit(f"已有同名 Agent「{a['name']}」但模板不同，先手动处理")
                agent.description, agent.config = a["description"], config
                await agent.save(update_fields=["description", "config", "updated_at"])
            self.agent_ids[a["name"]] = agent.id
            logger.info("Agent 就绪：%s", a["name"])

    async def workspaces(self) -> dict[str, UUID]:
        ids = {}
        for w in self.bundle["workspaces"]:
            supervisor = self.local_config(w["supervisor"])
            ws = await Workspace.filter(created_by=self.admin, name=w["name"]).first()
            if ws is None:
                ws = await Workspace.create(
                    created_by=self.admin, name=w["name"], description=w["description"],
                    avatar_url=w["avatar_url"], supervisor=supervisor, config=w["config"],
                )
            else:
                ws.description, ws.supervisor, ws.config = w["description"], supervisor, w["config"]
                await ws.save(update_fields=["description", "supervisor", "config", "updated_at"])
            for m in w["members"]:
                agent_id = self.agent_ids[m["agent"]]
                member = await WorkspaceMember.filter(workspace=ws, agent_id=agent_id).first()
                if member is None:
                    await WorkspaceMember.create(workspace=ws, agent_id=agent_id, config=m["config"])
                else:
                    member.config = m["config"]
                    await member.save(update_fields=["config", "updated_at"])
            ids[w["name"]] = ws.id
            logger.info("工作空间就绪：%s（%d 名成员）", w["name"], len(w["members"]))
        return ids

    async def run(self) -> dict[str, dict[str, str]]:
        await self.models(await self.providers())
        await self.knowledge_bases()
        await self.agents()
        ws_ids = await self.workspaces()
        return {
            scene: {
                "kind": s["kind"],
                "target_id": str(self.agent_ids[s["name"]] if s["kind"] == "agent" else ws_ids[s["name"]]),
            }
            for scene, s in self.bundle["scenes"].items()
        }


# ==================== 入口 ====================

def _parse_scenes(values: list[str]) -> dict[str, tuple[str, str]]:
    scenes = {}
    for item in values:
        scene, _, target = item.partition("=")
        kind, _, target_id = target.partition(":")
        if not (scene and kind and target_id):
            raise SystemExit(f"--scene 格式应为 名字=agent|workspace:编号，收到：{item}")
        scenes[scene] = (kind, target_id)
    return scenes


async def _main(args: argparse.Namespace) -> None:
    setup_logging()
    await pg_client.connect()
    try:
        if args.command == "export":
            out = Path(args.out_dir)
            out.mkdir(parents=True, exist_ok=True)
            await _Exporter(out).run(_parse_scenes(args.scene))
        else:
            root = Path(args.bundle_dir)
            bundle = json.loads((root / BUNDLE_FILE).read_text())
            secrets = json.load(sys.stdin)
            admin = await User.get(username=settings.ADMIN_USERNAME)
            scenes = await _Importer(root, bundle, secrets, admin).run()
            print("DEMO_SCENES=" + json.dumps(scenes, ensure_ascii=False, separators=(",", ":")))
    finally:
        await pg_client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="演示场景数据导出 / 导入")
    sub = parser.add_subparsers(dest="command", required=True)
    exp = sub.add_parser("export", help="源环境：导出场景依赖到目录")
    exp.add_argument("out_dir")
    exp.add_argument("--scene", action="append", required=True, help="名字=agent|workspace:编号")
    imp = sub.add_parser("import", help="目标环境：从目录导入，密钥从 stdin 读")
    imp.add_argument("bundle_dir")
    asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    main()
