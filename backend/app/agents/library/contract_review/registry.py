"""企业工商信息查询：工商数据服务的查询入口。演示数据写在代码里，生产环境对接工商数据 API。"""

from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.tools.base import CoCoTool, ToolCategory


@dataclass(frozen=True)
class CompanyRecord:
    name: str
    credit_code: str
    status: str
    legal_representative: str
    registered_capital: str
    established: str
    address: str


COMPANIES = (
    CompanyRecord(
        "南湾智造装备有限公司", "91330110MA7H2K3Q5N", "存续（在营、开业、在册）",
        "周明远", "5000 万元人民币", "2019-04-16", "浙江省杭州市余杭区仓前街道文一西路 1866 号",
    ),
    CompanyRecord(
        "北辰云港物流股份有限公司", "91320214MA1W8PXR3T", "存续（在营、开业、在册）",
        "林嘉禾", "1.2 亿元人民币", "2016-09-02", "江苏省无锡市新吴区长江北路 288 号",
    ),
    CompanyRecord(
        "东屿数联信息技术有限公司", "91440300MA5F6T1C8L", "注销",
        "陈立", "1000 万元人民币", "2018-01-10", "广东省深圳市南山区科技园科苑路 15 号",
    ),
)

_NOT_FOUND = "工商信息中没有查到这家企业。请核对合同中的甲方全称是否完整、准确。"


def _format(c: CompanyRecord) -> str:
    return (
        f"企业名称：{c.name}\n统一社会信用代码（税号）：{c.credit_code}\n经营状态：{c.status}\n"
        f"法定代表人：{c.legal_representative}\n注册资本：{c.registered_capital}\n"
        f"成立日期：{c.established}\n注册地址：{c.address}"
    )


class CompanyLookupInput(BaseModel):
    company_name: str = Field(description="合同中的甲方全称，如「南湾智造装备有限公司」")


class CompanyLookupTool(CoCoTool):
    name: str = "lookup_company_registry"
    display_name: str = "查询工商信息"
    description: str = "按企业全称查询工商登记信息：统一社会信用代码、经营状态、法定代表人、注册地址。"
    category: ToolCategory = "data_source"
    args_schema: type[BaseModel] = CompanyLookupInput

    async def _execute(self, company_name: str) -> str:
        name = company_name.strip()
        hit = next((c for c in COMPANIES if c.name == name), None)
        return _format(hit) if hit else _NOT_FOUND
