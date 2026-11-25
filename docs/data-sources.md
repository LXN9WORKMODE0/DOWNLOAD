# 数据源、配置与续跑

客户端记录中的 workflow 对应下列各节。脚本根目录和本机 Python 解释器见 .local/workstation-fc01.json。接手机器先同步管理仓库，核对负责范围、可用副本和远端未完成请求。对于标记为本地来源的脚本，由原客户端私下提供相同脚本及必要状态文件，再配置接手机器的输出、临时目录和凭据。

## ifs-mars

公开的 ECMWF 年度分组以 [plan.json](../plan.json) 定义组别、时段、区域、层次、变量和步长。使用 [仓库入口](../README.md) 的 run.ps1／download.py，经 ECMWF Web API 向 MARS 下单。使用有档案权限的账户，凭据从本机 .ecmwfapirc 或 .env 读取。先预览，按目录成本选择每批起报数，逐单提交。年度验收需要分组所需产品流均有相符的 GRIB 和 verified.json，再用 catalog.py register-year 登记。

本机早期 103–108°E、26–31°N MARS oper/scda 任务走 predict 工作流。oper 对应 00/12 UTC，scda 对应 06/18 UTC，区域 0.25°，配置以该任务原请求为准。两类产物都关联 ifs-mars。

## ifs-ens

从本地 Predict 根运行 `python download_ecmwf_ifs_ens.py --year 2025 --inventory` 只读查看起报范围。脚本按日期 × 00/12 UTC 即时生成任务，00 UTC 对接 Dynamical 的 0.25°公共档案，12 UTC 使用 ECMWF 公共镜像及 Source Cooperative GRIB 索引，按 HTTP Range 取报文。2025 年的任务不需要提供账户。依赖 Python、requests、numpy、ecCodes、netCDF4、dynamical-catalog 和其 Icechunk 依赖。源代码文件包含请求配置，环境、下载日志及 data/ 路径属于本机。

共享范围为 72–137°E、0–55°N，0.25°，控制成员加 50 个扰动成员。2t 预报时效 0–72h，每 6h；tp 为 6 小时区间，共 12 段。原始字段被裁剪、整理为 NetCDF4。每次起报应有 1,275 个成员 × 变量/时效组合，验收使用 missing_field_keys，并核对参考时间、网格和成员/时效轴。读取 .part 时等待原进程完成写入。脚本会跳过任何非空正式文件。续跑先用 inventory 找出缺失、部分和不可读起报，核对原日志后将缺损文件移至单独目录，再按 --date 或 --start/--end 与 --cycles 补齐。当前进程退出且范围确认后，可从同一资产根以 `python download_ecmwf_ifs_ens.py --year 2025` 继续。

## predict

本地 Predict 使用 download_config.toml 定义 103–108°E、26–31°N 的区域预报。配置的请求字段、层次、规则保留在脚本和 TOML。与绝对路径凭据同存的本机 TOML 以独立公开参数表供查阅。输出层分为下载、裁剪和处理后的结果。依赖见本地 requirements.txt；整理 NetCDF/GRIB 还需要 xarray、numpy、netCDF4、cfgrib 与 ecCodes。

| 产品 | 来源与认证 | 分块与核验 |
|---|---|---|
| IFS Open Data | ECMWF 公共目录，无账户。forecast_download.py ecmwf-open | 日期 × 起报时次；按变量取 GRIB，保持全球网格，核对请求、大小与 SHA-256 |
| IFS MARS | ECMWF MARS，需档案账号。run_source_worker.py ecmwf | 区分 oper/scda 的日期块；核对 GRIB2、请求回执及大小，单独处理远端待返回订单 |
| GFS | NOAA NOMADS、NCAR GDEX/RDA，公开下载，RDA NCSS 默认裁剪 | 起报 × 时效；2023 年 00/12 UTC、0–240h/3h；其他年度 00/06/12/18 UTC，0–240h/3h 与 252–384h/12h。核对区域 NetCDF 可读性及目标变量、坐标、时效；数据库和文件大小用于复核进度 |
| GEFS | NOAA AWS Open Data，公开索引 | 日期 × 起报 × 成员；00/06/12/18 UTC，c00+p01–p30，0–384h/6h。核对 65 个裁剪文件、GRIB 字段和完成标记总字节 |
| TIGGE | ECMWF ECDS，需要账户及条款授权，配额按来源 | CMA 控制成员按日期请求，配置 0.5°、00/06/12/18 UTC，0–384h/6h，时效和变量按目录实际可用性。历史 ecmf/kwbc 文件各有请求。先核对 ECDS 返回，各源的净辐射变量按原意义验收 |

原查询入口 forecast_download.py 提供 --dry-run。任务型下载由 download_manager.py 中 prepare_year 生成年份任务，下载状态存 SQLite。续跑前查 task_key、target、done、downloaded、remote_pending 和旧日志。复用已有 DB 和输出时，应从同一工作根恢复；接手部分范围时只给 worker 提供已分配的任务，原 run_source_worker.py 会处理所选来源的整个队列。GFS 的 2023 专用入口为 run_gfs_2023.py。其他历史任务按来源用 `python run_source_worker.py <source>`，先确认无同源 worker，且旧远端请求和任务恢复已经核对。对临时错误使用该管理器的重排机制，归档确认缺档的时次单独登记。GEFS 标记、GFS NetCDF 和 MARS/TIGGE GRIB 的计数单位不同。

## earthdata

NASA GES DISC 目录标识和各产品变量见[数据集索引](../catalog/research/index.json)。全国任务通过 NASA Harmony，目标 2019-12-31～2026-01-01，18–54°N、72–136°E，源网格 NetCDF。GLDAS 三小时一文件，MERRA-2 每产品每天一文件，文件内小时序列。原工作目录运行 `python -u china_harmony_download.py`。依赖 requests、numpy、netCDF4。本机 .env 配置 Earthdata Login 凭据，具体登录读取方式与限额见原脚本。使用 full_inventory.json 和 download_manifest.json，按产品与自然月生成 444 批，至多 3 个裁剪任务和 3 连接，本地保留 batch_jobs/。同一标签查找已提交作业，验证变量、网格、内部时间和有效数值后写 verified_files.jsonl。重启时复用大小与修改时间匹配的文件，并补 failed_downloads.json 中的缺项。此前区域历史资产源自 GES DISC 子集清单，旧 HTTP_services.cgi 已停用；恢复旧范围时用 Harmony 的等价变量和区域重新生成清单，经确认后补缺。

## cds

全国 ERA5 单层以 CDS 的 reanalysis 产品提供 0.25° GRIB。目标为 18–54°N、72–136°E、2019-12-31～2026-01-01，共 52,656 小时，按月加两个边界日共 74 件。共享变量见[参数表](parameters.json)。代码由 `workstation-fc01` 原脚本工程保管；在该工程根运行 `python -u era5_china_download.py`，依赖 requests、ecCodes、numpy，凭据由本机 CDS 客户端配置读取。每次一单，已有请求先通过本机 requests/ 记录查询。已有文件核对请求和验收记录，缺失时核对目录后再补；验收检查变量、单位、统计类型、时空网格和重复/缺失消息，保存 SHA-256。下载器把 HTTP 拒绝、队列和已验文件分开记录。

该任务要求本地直连：CDS API 会话和下载会话均关闭 requests 的 `trust_env` 并清空会话代理，因此不读取 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`，也不采用系统代理发现。下载会话不携带 CDS API 凭据，仅请求 CDS 结果资源；`network_connections.jsonl` 记录实际结果主机的远端 IP/端口。此设置不修改操作系统代理。本机的 `.part.transfer.json` 保存结果 URL 的主机、路径和预期字节数；只有同一结果可响应 Range 且 Content-Range 与本地前缀相符时才续传，否则会重建临时文件。CDS 结果过期时记录旧 ID 并对原选择重新下单，提交响应不确定时先查询匹配请求。2026-11-25 恢复现场时，已验收 2019-12 缓冲包；2020-01 包正在直连传输，遇到服务器中断后按 Range 续传，未验收前仍算缺项。详见[任务接入说明](tasks/era5-china.md)。ERA5-Land 全国只发现样本方案，样本入口为 `era5_validate_samples.py`，会发送真实请求；本次全量 ERA5 运行期间不新增 ERA5-Land 请求。

旧区域 ERA5 和 ERA5-Land 使用 CDS API/cdsapi，配置在 ERA5.py、ERA5-LAND*.py，范围 26–31°N、103–108°E。ERA5 老库存为按月 ZIP 内的小时 NetCDF，ERA5-Land 老库存按月份 × 四个变量组存 ZIP。旧脚本重试 CDS 请求，使用前比对历史 ZIP 与新请求变量，检查月份小时和网格；ZIP 的 CRC 只能证明压缩包成员可读。旧脚本的输出目录按本地配置调整。各产品需各自接受 CDS 条款，队列与请求限额以 CDS 现行规则为准。

## gdas

文件名对应 NOAA NCEP GDAS/FNL 0.25°，归档可通过 NSF NCAR GDEX 查找。保存 GRIB2 及同名 .idx。按起报（00/06/12/18 UTC）与 f00/f03 核对覆盖。原本地 GDAS_MERGE.py 是后处理入口，原始获取命令待确认。若需复现，从归档目录核对相同产品、起报与时效，下载后校验索引消息、文件可读性及原目标变量。

## storage

CMFD v2、CRA40-Land、CLDAS、1 km 栅格和模型资料本轮按保存资产登记。原获取方式待确认，已有解包目录和压缩包作为不同位置登记。CMFD 以变量 × 时间聚合 × 日期核对 NetCDF，CRA40-Land/CLDAS 按时间片 × 变量核对，模型资料按批次、站点、时间和工程格式核对。当前资产状态给出了已验证层级。
