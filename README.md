# 批量生成海报

## 如何使用

上传一张风景照。想在海报上写什么，就把文案一起发来；只发照片也可以，Skill 会根据画面自由拟写标题和配文。

Skill 会先写好 **24 份可查看的最终 Prompt**，每款一份。随后逐款生成小样，你会在两张概览图里看到 **24 个候选方案**。**A 有 12 款多彩海报，B 有 12 款三色海报**。从中任选一款，回复「我选三色第 11 款」或「B11」，就会收到这一款的高清海报。

### 选款示例

**1. 上传原照，告诉它你想写什么。** 这次只指定地名，其他文案交给 Skill。

> 把这张海岸照片做成海报。请保留标题「Sydney Watson Bay」，其他文案你来配。

[<img src="examples/sydney-watson-bay/coastal-photo.jpg" width="320" alt="Sydney Watson Bay 海岸原照。左边是海，右边是砂岩岬角、崖顶住宅和步道上的行人。">](examples/sydney-watson-bay/coastal-photo.jpg)

**2. 看两张概览，挑喜欢的一格。** 两张图里的相同编号对应同一种排版，点开可以放大比较。

| A · 多彩 12 款 | B · 三色 12 款 |
| --- | --- |
| [![多彩海报 A01 至 A12 选款总览](examples/sydney-watson-bay/a-overview.webp)](examples/sydney-watson-bay/a-overview.webp) | [![三色海报 B01 至 B12 选款总览，本例选中第三行第三列的 B11](examples/sydney-watson-bay/b-overview.webp)](examples/sydney-watson-bay/b-overview.webp) |

**3. 回复你的选择，拿到高清海报。** 这次选的是三色总览第三行、第三列的 B11。

> 我选三色第 11 款，帮我把这张做成高清海报。

[<img src="examples/sydney-watson-bay/b11-coast.png" width="480" alt="B11 高清海报。同一处岬角沿 COAST 字样由近至远出现三次，近处岩壁呈陶土橙色。">](examples/sydney-watson-bay/b11-coast.png)

[打开 B11 高清 PNG（1086 × 1448）](examples/sydney-watson-bay/b11-coast.png) · [查看这张海报实际使用的提示词](examples/sydney-watson-bay/b11-prompt.md)

## 生成原理

**先读照片，再排文字。** Skill 会观察原图哪里疏、哪里密，哪些轮廓能托住文字，哪些细节让人一眼认出现场。上面的海岸照左侧是开阔的海面，右侧的岬角有清楚的边缘。B11「斜轴上的分身」沿这条边取出岬角，让它顺着 **COAST** 的斜线由大到小出现三次。换一张照片，取景、断行和字位都会随之调整。[查看 12 种构图的选择依据](references/layout-selection.md)

**同一套排版，尝试两种配色。** 多彩系列的每一款都可以自由搭配颜色。三色系列则为这张照片选出三个色族，按整张画面的可见面积分配：约 **60% 主色**定基调，**30% 辅色**撑起文字和主体，**10% 点缀色**引导视线。这组海报用贝壳白留出天空，用深海青画出字和岬角，把陶土橙留给最近的岩壁。换一张照片，会重新取色。

**先写完 24 份最终 Prompt。** 每个编号都针对原照重新写六项设计决定：表现方式（Mode）、用色（Ink）、构图（Layout）、字体（Type）、图像处理（Process），以及这张照片独有的图文关系（Originality）。你可以在出图前打开这些指令。每份指令与原照一起独立生成一张小样，拼版工具按编号把小样排进两张总览。

**选定后只渲染一款高清海报。** Skill 读回入选小样实际使用的 Prompt，保留六项设计决定，并把需要恢复的细节写进高清 Prompt。生图时同时参考原照与入选小样，最后核对文案、构图与点缀色的位置。[打开交互构图图谱](references/atlas.html)
