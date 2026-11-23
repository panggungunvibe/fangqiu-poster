# 访秋海报

“访秋海报”是一个可持续扩展的照片艺术海报 Skill 项目。它保留用户原始照片的真实质感，通过确定性的选片、裁切和合成脚本完成视觉设计，而不是重新生成照片内容。

## 当前风格

### 树影风景拼贴

将 6–12 张风景照片嵌入固定枯树骨架，让枝干成为照片之间的自然分隔。输出为 `1206 × 2310` 竖版 PNG。

- 所有换图边界沿树枝发生，不使用普通矩形或多边形拼接。
- 自动控制主窗面积，避免单一切片吞掉画面。
- 高饱和橙红色素材只进入小窗，保持整体视觉平衡。
- 支持焦点裁切、自动选片和统一调色。

详细说明见 [`styles/tree-scape-collage/SKILL.md`](styles/tree-scape-collage/SKILL.md)。

## 安装

```bash
git clone https://github.com/panggungunvibe/fangqiu-poster.git ~/.codex/skills/fangqiu-poster
python3 -m pip install -r ~/.codex/skills/fangqiu-poster/requirements.txt
```

安装后可在 Codex 中使用：

```text
使用 $fangqiu-poster 把我上传的照片制作成访秋海报。
```

## 项目结构

```text
fangqiu-poster/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── styles/
│   └── tree-scape-collage/
│       ├── SKILL.md
│       ├── agents/
│       ├── assets/
│       └── scripts/
└── requirements.txt
```

## 增加新风格

每种风格放在独立的 `styles/<style-name>/` 目录中，并包含自己的 `SKILL.md`。只有确实需要的脚本、说明或固定视觉素材才放入该风格目录。新增完成后，同时更新根目录 `SKILL.md` 的风格路由和本 README 的风格列表。

风格名称使用小写英文、数字和连字符，用户看到的中文名称写在该风格的 `agents/openai.yaml` 中。

## 隐私

仓库不包含用户照片或已生成的个人海报。合成脚本在本地处理输入图片。

## License

[MIT](LICENSE)
