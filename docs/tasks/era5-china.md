# era5-china：全国 ERA5 单层逐小时资料

本任务按[接入指南](../task-onboarding.md)登记在研究目录，负责人为 `workstation-fc01`，项目 `r-forcing`、产品 `era5`、流程 `cds`。复用既有任务 ID `era5-china` 和存储代号 `earthdata-data`。接手机器须先核对该客户端的进程、远端订单及本地状态，不能另领同一范围重复下载。

## 目标与分块

| 项目 | 配置 |
|---|---|
| CDS 数据集 | `reanalysis-era5-single-levels` |
| 产品类型 | `reanalysis`，ERA5 单层确定性再分析 |
| 空间范围 | 18–54°N、72–136°E；CDS 顺序 `[54,72,18,136]`（北、西、南、东） |
| 发布网格 | 0.25°，纬度×经度为 145×257，纬度从北向南 |
| 时间 | 2019-12-31 00:00 至 2026-01-01 23:00 UTC，含首尾；完整 2020–2025 年前后各一天 |
| 计数 | 2,194 天、52,656 小时；每小时 15 个参数，共 789,840 条 GRIB 消息 |
| 交付分块 | 2020–2025 年的 72 个整月包，加首尾缓冲日各一包，共 74 包 |
| 格式 | 原始 GRIB；文件名 `era5_YYYY-MM.grib`，首尾月份实际各只含一个缓冲日 |
| 网络 | 本地 HTTPS 直连；API 和数据传输的 requests 会话均设置 `trust_env=False`、空代理配置，忽略系统代理及代理环境变量 |
| 并发 | CDS 任务严格串行；同一时刻只处理一个月包 |

机器可读配置见[参数表的 era5-china](../parameters.json)。这个区域与仓库五组 MARS 预报的默认区域不同，不能套用 `plan.json` 的范围、起报或时效配置。

## 参数与物理含义

| 物理量 | CDS 名称 | paramId | 原始单位 |
|---|---|---:|---|
| 2 米气温 | `2m_temperature` | 167 | K |
| 2 米露点温度 | `2m_dewpoint_temperature` | 168 | K |
| 地表气压 | `surface_pressure` | 134 | Pa |
| 10 米东西向风 | `10m_u_component_of_wind` | 165 | m/s |
| 10 米南北向风 | `10m_v_component_of_wind` | 166 | m/s |
| 总降水 | `total_precipitation` | 228 | m |
| 降雪水当量 | `snowfall` | 144 | m of water equivalent |
| 地表向下短波 | `surface_solar_radiation_downwards` | 169 | J/m² |
| 地表净短波 | `surface_net_solar_radiation` | 176 | J/m² |
| 地表向下长波 | `surface_thermal_radiation_downwards` | 175 | J/m² |
| 地表净长波 | `surface_net_thermal_radiation` | 177 | J/m² |
| 第一层土温 | `soil_temperature_level_1` | 139 | K，0–7 cm |
| 第二层土温 | `soil_temperature_level_2` | 170 | K，7–28 cm |
| 第三层土温 | `soil_temperature_level_3` | 183 | K，28–100 cm |
| 第四层土温 | `soil_temperature_level_4` | 236 | K，100–289 cm |

总降水包含雪。风速和比湿不作为独立参数下载，需要时分别由风分量、露点和气压推算。各模型土层定义不同，不能把 ERA5 四层直接等同于 GLDAS 或 MERRA-2 土层。

气温、气压、风和土温为瞬时量；降水和辐射为截至有效时刻的前一小时累计量，00 UTC 的统计区间落在前一天。保留原始值、符号与时间，不在下载阶段差分或转换单位。后续降水由 m 换为 mm，小时辐射由 J/m² 除以 3,600 换为 W/m²。ERA5-Land 的累计规则不同，不能复用它的日内差分公式。

## 代码、认证与执行位置

代码由 `workstation-fc01` 的本地 ERA5/地表驱动下载工程保管，本仓库同步参数、说明和索引；本页不表示代码或续跑状态已迁入本仓库。脚本和 Python 路径记录在该机忽略版本控制的 `.local/workstation-fc01.json`；输出根由 `.local/locations.json` 的 `earthdata-data` 映射。

所需脚本：`era5_china_download.py` 及其依赖模块 `era5_validate_samples.py`。后者导出变量、认证和 JSON 工具；导入不下单。不要单独启动混合样本脚本，否则会重新调度 ERA5-Land。

依赖：Python 3.12、`cdsapi`、`ecmwf-datastores-client`、`requests`、`numpy`、`eccodes`。有一个本机 CDS 账户，凭据保留在用户目录 `.cdsapirc`，并满足 CDS 对产品访问和许可的要求。NASA Earthdata Token 不用于此任务。

所有以下命令均在负责客户端的原脚本工程根目录执行，`python` 使用其已验证环境；不是在 DOWNLOAD 仓库根运行。

**只读预览，不提交订单：**

```shell
python -c "import era5_china_download as d; t=d.tasks(); print({'files':len(t),'hours':sum(len(x['dates'])*24 for x in t),'first':t[0]['request'],'last':t[-1]['request']})"
```

**启动或续跑，会访问 CDS，必要时提交真实订单：**

```shell
python -u era5_china_download.py
```

脚本有输出根单实例锁。先确认旧进程退出，保留原输出根和 `requests/`，才可重新启动；已核验文件会按大小和修改时间复用，变化后重新解码。需要停止时，在任务目录创建空文件 `STOP_DOWNLOAD`；原进程退出后移除它即可按同一命令续跑。停止本地进程不表示远端订单被取消。

## 存储、状态和错误恢复

任务根相对于 `earthdata-data` 为 `runs/era5_china_72_136_18_54_2020_2025/`：

| 本地文件或目录 | 用途 |
|---|---|
| `downloads/` | 正式 GRIB 与传输中的 `.part` |
| `requests/YYYY-MM.json` | 请求参数、远端 ID、历史、逐文件核验摘要和 SHA-256 |
| `download_manifest.json` | 固定区域、日期、15 个变量与分块 |
| `download_progress.json` | 文件数、已核验小时数、当前月份、直连标志和状态 |
| `download_process.json` | 启动 PID；不能仅凭该文件判断进程仍在运行 |
| `download.log`、`download_error.log` | 运行与错误日志，仅保留本机 |
| `network_policy.json`、`network_connections.jsonl` | 直连配置与实际数据连接记录，仅保留本机 |
| `*.part.transfer.json` | 未完成传输的远端资源身份和大小，用于安全续传 |

`accepted` 是远端排队，`running` 是远端处理，`downloading` 是本地传输，`validating` 是本地核验；它们不能计作已完成。进程不存在或日志不再更新时，必须重新查询保存的订单状态。排队和文件落盘分开统计，`.part` 不计入资产完成数。

请求或查询连续无进展失败最多重试三次；传输中断但已新增落盘字节时继续断点恢复，不消耗无进展失败次数。队列配额明确拒绝时等待 60 秒再提交。结果已过期时记录旧任务并重新申请同一选择；提交响应丢失时先按参数匹配已有任务，不能唯一匹配就停止。直连传输中断保留已落盘前缀；同一资源和预期大小匹配时发送 HTTP Range，并检查 Content-Range，服务器不支持 Range 则从头接收。原有无身份记录的 `.part` 不能安全续传，会重建。

2026-11-25 23:06 CST 的同步快照：已验收 1/74 包、24/52,656 小时、26,869,680 字节；2020-01 包正以直连 HTTPS 传输，观测到 14,680,064/832,960,080 字节。曾发生 HTTPS 响应中断，当前按 Range 续传。包括当前包在内的 73 包仍计作缺项，直到完整下载且 GRIB 逐报文验收通过。实际连接观察到 `136.156.139.54:443` 和 `136.156.136.3:443`。公开任务记录使用当次实际观测的进度；远端生成成功、下载完成和本地验收完成是不同状态。请求 ID、原始日志、凭据、绝对路径和原始数据均不提交到本仓库。ERA5-Land 仍保持暂停新增请求，已验证样本另归 `era5-land-sample`。

## 验收和交接

每包先写 `.part`，逐条读取全部 GRIB 报文，核对 15 个 paramId、单位、瞬时/累计类型、145×257 网格和坐标、日期与整点小时、有限有效值，以及每个参数×有效小时恰好一条。全量应有 789,840 条消息。通过后才改为正式文件名并登记大小、mtime、SHA-256；只有 74 包和 52,656 小时全部通过才标为 `complete`。

目录预览和 `catalog.py locate` 只检查配置或挂载，不能代替内容验收。当前完成资产的覆盖必须逐条引用本地回执，不能将目标全时段写成已有覆盖。其他机器接手须完整复制数据、请求回执、清单、续跑及传输状态，并确认旧进程已停及远端订单归属，然后更新同一任务的负责人。

在 DOWNLOAD 仓库根运行以下命令检查索引与挂载；它们不下单：

```shell
python catalog.py validate
python catalog.py locate --client workstation-fc01 --task era5-china
```

参考：[CDS ERA5 产品](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels)、[ERA5 数据说明](https://confluence.ecmwf.int/display/CKB/ERA5%3A+data+documentation)。
