"""Generate Sankey diagram for coding agent failure attribution."""
import plotly.graph_objects as go

# === Data: 10 experiments, 109 total score points lost ===
#
# 需求理解错误 group (5 experiments, 62+2=64 points lost):
#   Opus Short (1/1/0), Opus Short Loop (2/1/1), CodeArts Long (1/0/0),
#   Lingxi Long (1/1/0), OpenCodeGLM Short (1/1/0)
#
# 上下文感知不足 group (5 experiments, 45 points lost):
#   Opus Long (4/2/2), Opus Long Loop (4/3/2), CodeArts Short (2/2/1),
#   Lingxi Short (2/1/1), OpenCodeGLM Long (2/1/1)

labels = [
    # Layer 0: Root Causes
    "需求理解错误\n(6/10 实验)",          # 0
    "上下文感知不足\n(5/10 实验)",         # 1
    "模型能力不足\n(2/10 实验)",           # 2
    # Layer 1: Failure Modes
    "功能方向完全错误",                    # 3
    "API 设计偏差\n(扁平 vs 嵌套)",       # 4
    "文件/模块遗漏\n(验证·降级·生命周期)", # 5
    "测试与验证缺失\n(e2e·validation)",    # 6
    "实现策略保守\n(不改签名·不重构接口)",  # 7
    "编译级错误\n(语法·缩进·未定义)",      # 8
    # Layer 2: Score Impact
    "A 功能正确性 损失\n(共 30 分)",       # 9
    "B 完整性 损失\n(共 37 分)",           # 10
    "C 行为等价性 损失\n(共 42 分)",       # 11
]

node_colors = [
    # Root Causes
    "#d32f2f",  # 需求理解错误 - red
    "#ef6c00",  # 上下文感知不足 - orange
    "#7b1fa2",  # 模型能力不足 - purple
    # Failure Modes
    "#c62828",  # 功能方向完全错误 - dark red
    "#e65100",  # API设计偏差 - deep orange
    "#f57c00",  # 文件遗漏 - orange
    "#ff8f00",  # 测试缺失 - amber
    "#fbc02d",  # 实现策略保守 - yellow
    "#6a1b9a",  # 编译错误 - dark purple
    # Score Impact
    "#1565c0",  # A - blue
    "#00838f",  # B - teal
    "#2e7d32",  # C - green
]

# Links: (source, target, value)
links = [
    # Root Cause → Failure Mode
    (0, 3, 62),   # 需求理解错误 → 功能方向完全错误
    (1, 4, 12),   # 上下文感知不足 → API设计偏差
    (1, 5, 10),   # 上下文感知不足 → 文件/模块遗漏
    (1, 6, 6),    # 上下文感知不足 → 测试与验证缺失
    (1, 7, 17),   # 上下文感知不足 → 实现策略保守
    (2, 8, 2),    # 模型能力不足 → 编译级错误

    # Failure Mode → Score Impact
    (3, 9,  17),  # 功能方向错误 → A损失
    (3, 10, 21),  # 功能方向错误 → B损失 (cascade)
    (3, 11, 24),  # 功能方向错误 → C损失 (cascade)
    (4, 9,  3),   # API偏差 → A损失
    (4, 11, 9),   # API偏差 → C损失 (主要影响行为等价性)
    (5, 10, 10),  # 文件遗漏 → B损失
    (6, 10, 6),   # 测试缺失 → B损失
    (7, 9,  8),   # 策略保守 → A损失
    (7, 11, 9),   # 策略保守 → C损失
    (8, 9,  2),   # 编译错误 → A损失
]

sources = [l[0] for l in links]
targets = [l[1] for l in links]
values  = [l[2] for l in links]

# Link colors follow source node with transparency
color_map = {
    0: "rgba(211,47,47,0.35)",    # red
    1: "rgba(239,108,0,0.35)",    # orange
    2: "rgba(123,31,162,0.35)",   # purple
    3: "rgba(198,40,40,0.30)",    # dark red
    4: "rgba(230,81,0,0.30)",     # deep orange
    5: "rgba(245,124,0,0.30)",    # orange
    6: "rgba(255,143,0,0.30)",    # amber
    7: "rgba(251,192,45,0.30)",   # yellow
    8: "rgba(106,27,154,0.30)",   # dark purple
}
link_colors = [color_map[s] for s in sources]

fig = go.Figure(data=[go.Sankey(
    arrangement="snap",
    node=dict(
        pad=20,
        thickness=25,
        line=dict(color="black", width=0.5),
        label=labels,
        color=node_colors,
    ),
    link=dict(
        source=sources,
        target=targets,
        value=values,
        color=link_colors,
    )
)])

fig.update_layout(
    title=dict(
        text=(
            "Coding Agent 长程任务失败归因 — 桑基图"
            "<br><sup style='color:#666'>"
            "基于 10 次 KEP-5365 实验 | 满分 150 (10×15) | 实得 41 | 损失 109 分的因果追踪"
            "</sup>"
        ),
        font=dict(size=20),
    ),
    font=dict(size=13, family="Microsoft YaHei, PingFang SC, sans-serif"),
    width=1300,
    height=750,
    margin=dict(l=20, r=20, t=80, b=30),
    paper_bgcolor="white",
    annotations=[
        dict(x=0.01, y=-0.02, text="根因", showarrow=False,
             font=dict(size=14, color="#888"), xref="paper", yref="paper"),
        dict(x=0.46, y=-0.02, text="失败模式", showarrow=False,
             font=dict(size=14, color="#888"), xref="paper", yref="paper"),
        dict(x=0.95, y=-0.02, text="评分损失", showarrow=False,
             font=dict(size=14, color="#888"), xref="paper", yref="paper"),
    ]
)

out = "/Users/zihanwu/codes/latex/Secret Base/Assets/coding-agent-failure-sankey.html"
fig.write_html(out, include_plotlyjs=True)
print(f"Saved to {out}")
