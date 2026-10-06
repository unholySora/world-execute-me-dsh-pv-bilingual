# subtitles-zh/：中文译文字幕版

这里放两支在成片上叠加了中文译文字幕的同人版本，以及做出它们的全部脚本、数据和实测曲线。

底片用的是 B 站成片（[BV1xCai6aE9g](https://www.bilibili.com/video/BV1xCai6aE9g/)）的 1080p 版本。官方标称的
4K 实际是 720p 最近邻放大，1080p 已经是这支片子的真实上限。

## 两支片子

| 文件 | 说明 |
|---|---|
| `world_execute_me_zh_shared-box_1080p.mp4` | 第一版：中文显示在原片那个**共享输入框的右半边**——整句常驻、句尾一个闪烁光标 |
| `world_execute_me_zh_two-boxes_1080p.mp4` | 最终版：把原框体做成**左右两个各自独立、中间留缝**的输入框。左框放译文（右对齐、句尾闪烁光标、框内右下角「译文 · zh」）；右框是原片的英文框体，`stdout · tokens` 图例、`>` 提示符、逐词 chip、token 号全部是原片自己那份 |

两版都在 211.88 秒、1920×1080、24 fps，音频与原片一致。

## 英文那一半是怎么搬过去的

没有重画。每一帧从原片 band 里把已经画好的内容（含 `stdout · tokens` 图例）抠出来、整体平移再写回去，
所以右框里的英文与原片逐像素同源；腾出来的地方用同一行左右最近的背景像素插值补上（band 的底色带极淡渐变，
平涂会留下可见方块）。中文按原片自己的两条实测曲线渲染：框体在场程度（原片会把框体画淡、随音乐脉冲）
与文字亮度增益（原片抽掉系统色的段落）。全片有 7.3% 的时长原片根本没画这个框体，那些时刻整条透传、画面一个像素不改。

最终版里上一句会被打上删除横杠、快速左漂到左对齐并变暗留在那里，新句在右框显现——这个动画的时序、
漂移距离与横杠扫出比例都写在 `zh_band_boxes.py` 里（`DEL_LEAD` / `DEL_DUR` / `DEL_DIM`）。

## 自己跑一遍

```bash
export WEM_SOURCE=/path/to/1920x1080/source.mp4   # 必须 1080p：几何是按 1080p 量的
python zh_band.py render                         # 第一版 -> out/film_zh.mp4
python zh_band_boxes.py render                   # 最终版 -> out/film_zh_boxes.mp4
python zh_band_boxes.py render4k 0 211.875 film_zh_boxes_4k.mp4   # 4K 版（底片 lanczos 放大，文字层按 2 倍重渲）
```

- **字体**：英文用仓库里自带的 `film/ai_mascot_mv_world_execute_20260926/fonts/SpaceMono-Bold.ttf`（脚本会向上查找）；
  中文默认用系统 Noto Sans CJK，可用 `WEM_CJK_FONT=/path/font.ttc#2` 替换，等宽也可用 `WEM_MONO_FONT` 覆盖。
  原片英文用的是 Consolas、中文是微软雅黑，字形会略有差异——英文之所以没有这个问题，是因为它直接搬原片像素。
- **数据**：`zh_tracks2.json` 是逐句对齐结果（128 句，字段 `start`/`end`/`zh`/`en`，`en` 仅供对照）；
  `box_present.json` 与 `band_gain.json` 是从原片实测的两条曲线（12 fps，2543 个采样）。
- **歌词**：按仓库约定歌词不入库。本目录的 JSON 为了能直接复现，保留了英文原句与本目录作者做的中文译文；
  若不需要，可只留 `start`/`end`/`zh`。

## 许可与署名

- 本目录的脚本与文档沿用仓库的 MIT 许可；画面仍按 CC BY-NC-SA 4.0；音乐与歌词权利归 Mili，不在本目录许可范围内。
- 按仓库 README「分享视频」一节的要求：成片包含 AI 生成画面（原片舞者部分），且为非商业同人分享，
  保留完整署名链与许可链接。
- 字幕层与本文档由 unholySora 的 AI 助手（赫蒂）制作，方案取舍与逐批审片由 unholySora 完成。
