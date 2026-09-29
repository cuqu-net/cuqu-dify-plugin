# CUQU 找搭子（Dify 插件）

检索 **CUQU找搭子** 平台的实时线下活动：桌游、飞盘、徒步、羽毛球、二次元、钓鱼、读书会等
100+ 兴趣品类，覆盖深圳及中国 10+ 城市，含中国香港。

**只读工具，无需 API Key。**

## 工具

| 工具 | 返回内容 |
| --- | --- |
| `query_activities` | 按品类/城市/关键词/日期查近期未开始的场次，含标题、品类、日期时间、地点、判定城市、价格、报名进度、主理人与公开详情页链接 |
| `query_venues` | 近期真实办过 CUQU 活动的场地（由真实活动聚合而来），含办过哪些品类、场次数量、估算容量、活跃主理人 |

两个工具都优先返回未开始的场次；一旦上游出现占位数据的特征，工具会直接中止返回，
**绝不让 Agent 编活动**。

## 参数

### `query_activities`
- `activity_type` — 品类关键词（桌游 / 羽毛球 / 飞盘 / 徒步 / 钓鱼 / 二次元 等）
- `city` — 城市名不带"市"（深圳、广州、香港）；留空不限城市
- `keyword` — 自由文本，匹配标题、地点、品类
- `date` — 支持 周末 / 周六 / 周日 / 今天 / 明天 / 后天 / YYYY-MM-DD
- `limit` — 1–50，默认 20

日期无法识别时，**工具会在 note 里说明并忽略该过滤**，而不是默默返回空列表 ——
不能让 Agent 因为一句"周末"没解析成功就回答"没有活动"。

### `query_venues`
- `city`、`activity_type`、`min_capacity`

## 安装

**方式一（推荐）**：Dify Marketplace 搜索 *CUQU Activity Finder* 直接安装。

**方式二**：本地打包后离线安装

```bash
dify plugin package ./cuqu-dify-plugin    # 生成 cuqu_activity_finder.difypkg
```

Dify 后台 → 插件 → 安装插件 → 拖入 `.difypkg`。

## 数据来源与口径边界

- 实时数据来自 CUQU 公开活动接口 `https://cuqu.net/api/activity`
- 单次最多返回 **最近 100 条**，上游无可用分页参数 —— 结果是最新一段目录，不是全量归档
- 上游**没有 city 字段**：城市由 location 自由文本判定，并用经纬度对 38 个城市中心兜底
- **场地是聚合结果**：平台没有独立场地接口，因此只包含近期真实办过活动的场地；
  `estimated_capacity` 由历史场次的人数上限推断，非场地方官方容量
- 只读：不含报名、支付、签到等任何写操作

## 隐私

不存储数据、不索取凭据，详见 [PRIVACY.md](../PRIVACY.md)。

## 相关链接

- 官网：<https://cuqu.net>
- 源码：<https://github.com/cuqu-net/cuqu-dify-plugin>
- 联系：<liqi.cuhk@gmail.com>
