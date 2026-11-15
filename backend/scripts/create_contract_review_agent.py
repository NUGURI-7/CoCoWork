"""建「合同初审」公共 Agent：创建者和对话模型沿用一个现有的管理员 Agent。

业务 Agent 由管理员建、所有员工可用（见 services/agent/access.py）。这里直接复用
参照 Agent 的创建者（管理员）和模型配置，免得再去页面上点一遍。已经建过则只打印 ID。

    uv run python scripts/create_contract_review_agent.py --from-agent <参照 Agent ID>
"""

import argparse
import asyncio
from uuid import UUID

from app.agents.templates.builtin.contract_review import ContractReviewTemplate
from app.db.postgresql import PostgreSQLClient
from app.models import Agent
from app.schemas.agent.config_schema import AgentConfig


async def main(reference_id: UUID) -> None:
    client = PostgreSQLClient()
    await client.connect()
    try:
        reference = await Agent.get(id=reference_id)
        existing = await Agent.filter(
            template=ContractReviewTemplate.key, created_by_id=reference.created_by_id,
        ).first()
        if existing is not None:
            print(f"已存在：{existing.id}")
            return

        chat = AgentConfig.model_validate(reference.config).models.chat
        config = AgentConfig.model_validate({"models": {"chat": chat.model_dump(mode="json") if chat else None}})
        agent = await Agent.create(
            created_by_id=reference.created_by_id,
            name=ContractReviewTemplate.name,
            description=ContractReviewTemplate.description,
            template=ContractReviewTemplate.key,
            config=config.model_dump(mode="json"),
        )
        print(f"已创建：{agent.id}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-agent", type=UUID, required=True, help="参照 Agent 的 ID（取它的创建者和对话模型）")
    asyncio.run(main(parser.parse_args().from_agent))
