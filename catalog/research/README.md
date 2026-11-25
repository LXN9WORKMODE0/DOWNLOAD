# 研究数据目录

按下载指令浏览[任务总表](../../docs/tasks/README.md)。登记项目、数据源和产物时，参照[任务接入指南](../../docs/task-onboarding.md)和[客户端配置模板](../../templates/research-client.json)。

[研究项目和数据集](index.json)以 ID 关联。同一产品只建一个数据集，区域、日期、变量配置及副本写在各客户端的资产或任务里。当前客户端是 [workstation-fc01](clients/workstation-fc01.json)。其中 assets 是本地储备，tasks 是已有下载范围。各产品的配置与续跑见[数据源说明](../../docs/data-sources.md)。

全国 ERA5 单层任务复用 `r-forcing / era5 / cds`，进度和专门的直连、断点续传与验收说明见[era5-china 任务记录](../../docs/tasks/era5-china.md)。该任务分块不同于 ECMWF 预报年度组，不占用 `catalog/tasks.csv` 的年度 MARS 行。

原有 [ECMWF 年度任务](../tasks.csv)、[年度产物与历史位置](../assets.csv)和 [plan.json](../../plan.json)用于 MARS 确定性预报分组方案。新目录通过 ifs-mars 数据集与该方案关联，区域历史档案和年度分组有各自的范围及验收规则。尚未执行的组年组合保留为计划。

每台电脑按 [locations.example.json](../locations.example.json) 配置自己的 .local/locations.json，键为存储代号，值为实际根目录。资产路径相对于根目录。同一物理盘在不同电脑上可以映射同一个代号，不同副本各列一条资产。可在仓库根目录运行：

```powershell
python catalog.py locate
python catalog.py locate --client workstation-fc01
python catalog.py locate --client workstation-fc01 --task ifs-ens-2025
```

locate 核对挂载和路径可访问性。客户端记录中的核验状态来自相应产品的验收文件或清点结果。verified 表示本机在所述方法下核验，archive_checked 表示核验了归档容器，inventory 表示本机确认文件、目录或文件名范围，sample_checked 表示抽样，registered 表示沿用仓库记录，unmapped 表示尚无可用映射，offline 表示已知盘离线待核验。时间范围写明依据；文件名首尾可能包含缺期。进度表中的数据库完成数单独标注。

补取前先同步仓库，核对同产品的区域、时段、预报维度、存量副本及在途订单，再登记实际缺口。发生续传或转移存储位置时，更新原任务及资产明细，并在[总表](../../docs/tasks/README.md)同步最近状态。公开索引使用项目与存储代号，凭据、私有仓库地址、请求 ID、绝对路径和数据保存在本机。
