# 把一项新任务接入 DOWNLOAD

先确定任务的负责人在哪里登记，然后再填目标、执行方法和已有文件。下面的路径均从仓库根目录起算。

| 你要接入什么 | 在哪里登记 | 可直接参照的记录 |
|---|---|---|
| 已有 ECMWF MARS 五组方案中的年度任务 | 在 `plan.json` 核对组、年份和字段，在 `catalog/tasks.csv` 领取对应行。年度产物用 `catalog.py register-year` 登记至 `catalog/assets.csv` | `hydrodynamics-2024`。领取、暂停、续跑和年度验收见[客户端说明](clients.md) |
| 其他数据源、新区域或不同获取方法 | 在 `catalog/research/index.json` 关联项目和数据集，在负责机器的 `catalog/research/clients/<client>.json` 写一条任务 | `ifs-ens-2025` 按起报核验，`era5-china` 按月包或边界日核验。区域 MARS 的 `mars-regional` 使用 `predict` 流程，与五组年度方案分别管理 |
| 只有存量文件、旧盘或另一份副本 | 在研究目录的客户端文件中增加 `assets` 条目。可以省略 `task_id`。五组年度任务产物沿用首行的年度登记命令 | `workstation-fc01.json` 中的 CMFD 和模型资料。登记覆盖范围、清点方式及缺口即可 |

## 接入一项研究任务

1. **核对范围和重复任务。** 先同步主分支，查看[项目与产品](../catalog/research/index.json)、各客户端的 `tasks`、`assets` 和[年度任务](../catalog/tasks.csv)。按产品版本、区域、时间、变量及分块比对。同一范围已有负责人时，更新原记录或办理交接。两个客户端各做一部分时，写出互不重叠的日期、起报或成员范围，各用一个任务 ID。
2. **连接项目和产品。** 同一产品复用 `datasets[].id`。新项目填 `id/name/association/datasets`，归属待确认可直接注明。新增产品填 `id/source/product/version/type/workflow`，再把 ID 加入对应项目的 `datasets`。同一产品可以供多个项目使用。地区和日期变化通常只需新任务。
3. **填写负责客户端。** 首次登记一台机器时，复制[客户端模板](../templates/research-client.json)到 `catalog/research/clients/<client>.json`，将文件名和两处客户端代号一起替换；已有客户端只追加需要的条目。模板用已有的 `r-forcing / era5 / cds` 演示一个虚构的单日范围，演示日期、路径、进度和核验方法均须按实际填写。尚无产物时用 `"assets": []`，并在 `target` 中注明计划输出的存储代号和相对目录。
4. **说明如何执行。** `workflow` 对应[数据源说明](data-sources.md)的同名小节。复用已有流程时指明参数差异；新增流程时写明数据来源、依赖、认证方式、参数配置、工作目录、预览、启动、续跑和验收入口。公开参数放入[参数表](parameters.json)或链接已有配置。注明代码来自仓库哪个路径或由哪个客户端保管，区分只读盘点命令和会提交订单的命令。
5. **登记保存位置。** 复用已有存储代号，新代号加入 `catalog/locations.example.json`，共享示例值留空。每台机器在 `.local/locations.json` 填该代号对应的绝对根目录。资产的 `relative_path` 从该根起算，使用正斜杠。同一盘可跨机器共用代号，独立副本单列。公开仓库只保存配置、说明和索引；凭据、请求号、私有路径、原始文件与续跑状态保存在本机。
6. **验证并交接。** 在仓库根目录运行下方命令。合并前复核其他客户端是否已领取重叠范围。任务实际启动后更新 `status/updated`；有新盘点结果时同步 `observed_at/progress/gaps` 与对应资产。交接时原负责人先确认本地进程和远端请求，新负责人核对输出盘、队列或回执后接续同一任务 ID，并将权属变更一并提交。

## 任务与资产怎样填写

| 字段 | 填写口径 |
|---|---|
| `id / project / dataset / client` | 任务 ID 在各客户端间唯一，项目和产品引用索引中的 ID。多产品共用一个范围和流程时，`dataset` 可用数组，参见 `earthdata-regional` |
| `target / workflow` | 明确可验收的时间、区域、网格、变量及输出分块。预报另写起报、时效和成员，累计量写统计窗口。流程填该任务实际采用的方法 |
| `status / updated` | 新计划用 `planned`，实际运行用 `running`，有意暂停用 `paused`，按目标验收后用 `complete`。历史盘点保留 `inactive`、`stored` 的原意。记录观测日期或含时区时间 |
| `progress / gaps` | 至少写计数单位和方法。区分队列完成数、盘点数和经核验数。知道分母再填 `total`；缺哪些时段、是否有在途订单或哪些内容尚未核验写入 `gaps` |
| `assets[]` | 每份副本填 `dataset/storage_id/relative_path/kind/coverage/format/verification/notes`。能归到任务时附 `task_id`。写实际覆盖和核验依据，沿用[研究目录](../catalog/research/README.md)中的 `inventory`、`sample_checked`、`verified` 等层级 |

**实例。** 管理另一地区的 ERA5 单层资料时，可以继续使用 `era5` 和 `cds`，在负责客户端中增加目标区域、年月与变量；如果另一台电脑只是挂载原盘，配置同一存储代号即可。如果交付的是独立复制的一批文件，则登记新的存储位置、实际覆盖及核验依据。

## 交给本窗口登记时

其他项目可以按以下格式提供接入资料，一项任务一份。可直接引用已有配置、说明或验收记录。未知项写“待确认”，已有数据和当前运行状态请注明清点日期。

```text
项目与产品（已有 ID 可直接引用）
目标范围与可独立交接的分块
负责客户端、当前状态、清点日期
代码或配置入口、预览及续跑方法
目标存储代号与相对目录、已有副本及覆盖
计数单位、进度、缺口、完成判据与核验依据
```

## 合并前核对

```shell
python catalog.py validate
python catalog.py locate --client <client> --task <task-id>
```

请将尖括号及其中内容替换为实际代号。第一条离线检查项目、产品、流程、任务负责人、资产引用和相对路径。第二条在本机检查已关联资产的可访问性；尚未登记资产时无输出，未挂载时显示 `unmapped`。数据完整性由各产品的验收方法判定。年度 MARS 只有在规定产品流的 GRIB 和核验回执匹配后才登记 `annual_verified`。
