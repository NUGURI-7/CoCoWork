/**
 * 登录 / 注册页右列的产品演示动画 —— 一个循环播放的「假工作空间」。
 *
 * 画的是 CoCoWork 独有的那件事：supervisor 收到需求，把活拆给招募进来的成员，
 * 成员各自调工具干完，产出物落到面板里。**刻意不画流程图** —— 画布式编排是本项目
 * 明确否决掉的方向，拿它当门面等于宣传一个不存在的功能。
 *
 * 实现上是纯 CSS：所有动画写在 app.css 的 `cw-*` keyframes 里，共用一条 8s 时间轴
 * （见那里的注释）。这里只负责摆结构、给每个元素挂对应的 slot 名。
 * 没有 JS 定时器、没有图片、没有动画库 —— 登录页首屏不该为一块装饰付出运行时代价。
 */

import { Check, Crown, Database, FileImage, Terminal } from 'lucide-react'
import { ring } from 'ldrs'

ring.register()

/** 成员卡：头像色块 + 名字 + 正在调用的工具 + 右侧状态（转圈 ⇄ 打勾） */
interface MemberRowProps {
  name: string
  action: string
  icon: React.ReactNode
  /** 头像色块的 Tailwind 背景类 —— 两名成员靠颜色区分，对齐工作空间里的成员色块 */
  avatarClass: string
  /** 进场时机（slot-c 先、slot-d 后）与状态交接时机（1 先、2 后），都定义在 app.css */
  slot: 'cw-slot-c' | 'cw-slot-d'
  step: 1 | 2
}

function MemberRow({ name, action, icon, avatarClass, slot, step }: MemberRowProps) {
  return (
    <div className="relative">
      {/* 主干伸过来的横向支线：跟卡片同一时机出现，把「这张卡是被派出去的」画实 */}
      <span
        className="cw-cycle cw-dash-x absolute -left-5 h-0.5 w-5"
        style={{ animationName: slot }}
      />
      <div
        className="cw-cycle bg-card border-border/60 flex items-center gap-4 rounded-lg border px-4 py-3.5 shadow-sm"
        style={{ animationName: slot }}
      >
        <div
          className={`flex size-10 shrink-0 items-center justify-center rounded-md text-white ${avatarClass}`}
        >
          {icon}
        </div>

        <div className="min-w-0 flex-1 space-y-1">
          <div className="text-foreground truncate text-[16px] leading-tight font-medium">
            {name}
          </div>
          <div className="text-muted-foreground truncate font-mono text-[14px] leading-tight">
            {action}
          </div>
        </div>

        {/* 转圈与打勾叠在同一格，靠互补的可见窗口交接，避免布局跳动 */}
        <div className="relative size-5 shrink-0">
          <span
            className="cw-cycle cw-busy absolute inset-0 flex items-center justify-center"
            style={{ animationName: `cw-busy-${step}` }}
          >
            <l-ring size="20" stroke="2" speed="2" color="#2f6b53" />
          </span>
          <span
            className="cw-cycle bg-brand absolute inset-0 flex items-center justify-center rounded-full text-white"
            style={{ animationName: `cw-done-${step}` }}
          >
            <Check size={14} strokeWidth={3} />
          </span>
        </div>
      </div>
    </div>
  )
}

export default function WorkspacePreview() {
  return (
    <div className="w-full max-w-2xl">
      {/* 假窗口壳：三个点 + 状态标签，一眼认出是「一个正在跑的界面」 */}
      <div className="bg-card border-border/60 overflow-hidden rounded-xl border shadow-xl">
        <div className="border-border/60 bg-muted/40 flex items-center gap-2.5 border-b px-6 py-3.5">
          <span className="bg-muted-foreground/25 size-3 rounded-full" />
          <span className="bg-muted-foreground/25 size-3 rounded-full" />
          <span className="bg-muted-foreground/25 size-3 rounded-full" />
          <div className="text-muted-foreground ml-auto flex items-center gap-2 font-mono text-[14px]">
            <span
              className="bg-brand size-2 rounded-full"
              style={{ animation: 'cw-pulse 2s ease-in-out infinite' }}
            />
            workspace · running
          </div>
        </div>

        <div className="space-y-5 px-6 py-7">
          {/* ① 用户提问 */}
          <div className="cw-cycle flex justify-end" style={{ animationName: 'cw-slot-a' }}>
            <div className="bg-brand-subtle text-foreground max-w-[80%] rounded-lg rounded-br-sm px-4 py-3 text-[16px] leading-relaxed">
              帮我把这季度的数据整理一下，做张图
            </div>
          </div>

          {/* ② supervisor 分派 */}
          <div className="cw-cycle flex items-start gap-3" style={{ animationName: 'cw-slot-b' }}>
            <div className="bg-brand flex size-10 shrink-0 items-center justify-center rounded-md text-white">
              <Crown size={20} />
            </div>
            <div className="pt-1">
              <div className="text-foreground text-[16px] leading-tight font-medium">
                Supervisor
              </div>
              {/* 两段文案叠放：派活时「正在分派…」，成员都接手后换成结果，避免终态自相矛盾 */}
              <div className="relative mt-2 h-4 whitespace-nowrap">
                <div
                  className="cw-cycle cw-busy absolute inset-0 flex items-center gap-1"
                  style={{ animationName: 'cw-dispatching' }}
                >
                  <span className="text-muted-foreground text-[14px]">正在分派</span>
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="bg-muted-foreground size-1.5 rounded-full"
                      style={{ animation: `cw-typing 1.2s ease-in-out ${i * 0.16}s infinite` }}
                    />
                  ))}
                </div>
                <span
                  className="cw-cycle text-muted-foreground absolute inset-0 text-[14px] leading-4 whitespace-nowrap"
                  style={{ animationName: 'cw-dispatched' }}
                >
                  已分派给 2 名成员
                </span>
              </div>
            </div>
          </div>

          {/* ③ 两名成员：缩进 + 左侧生长的连线，表达「这两条是被派出去的」 */}
          <div className="relative pl-12">
            <span
              className="cw-cycle cw-dash-y absolute top-1 left-[19px] w-0.5"
              style={{ animationName: 'cw-thread' }}
            />
            <div className="space-y-3">
              <MemberRow
                slot="cw-slot-c"
                step={1}
                name="数据分析师"
                action="knowledge.retrieve"
                icon={<Database size={18} />}
                avatarClass="bg-sky-600"
              />
              <MemberRow
                slot="cw-slot-d"
                step={2}
                name="图表专员"
                action="skill.run · sandbox"
                icon={<Terminal size={18} />}
                avatarClass="bg-amber-600"
              />
            </div>
          </div>

          {/* ④ 产出物落地 */}
          <div
            className="cw-cycle border-brand-border bg-brand-subtle/60 flex items-center gap-3 rounded-lg border border-dashed px-4 py-3.5"
            style={{ animationName: 'cw-slot-e' }}
          >
            <FileImage size={20} className="text-brand shrink-0" />
            <span className="text-foreground font-mono text-[16px]">q3_revenue.png</span>
            <span className="text-muted-foreground ml-auto text-[14px]">已存入产出物</span>
          </div>
        </div>
      </div>
    </div>
  )
}
