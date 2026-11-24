# 研究数据目录

首次接入项目、数据源或客户端时，参照[任务接入指南](../../docs/task-onboarding.md)和[客户端配置模板](../../templates/research-client.json)。

[研究项目和数据集](index.json)以 ID 关联。同一产品只建一个数据集，区域、日期、变量配置及副本写在各客户端的资产或任务里。当前客户端是 [workstation-fc01](clients/workstation-fc01.json)。其中 assets 是本地储备，tasks 是已有下载范围。各产品的配置与续跑见[数据源说明](../../docs/data-sources.md)。

原有 [ECMWF 年度任务](../tasks.csv)、[年度产物与历史位置](../assets.csv)和 [plan.json](../../plan.json)用于 MARS 确定性预报分组方案。新目录通过 ifs-mars 数据集与该方案关联，区域历史档案和年度分组有各自的范围及验收规则。原表里无客户端下载负责人的年度任务继续按其登记状态管理。

每台电脑按 [locations.example.json](../locations.example.json) 配置自己的 .local/locations.json，键为存储代号，值为实际根目录。资产路径相对于根目录。同一物理盘在不同电脑上可以映射同一个代号，不同副本各列一条资产。可在仓库根目录运行：

```powershell
python catalog.py locate
python catalog.py locate --client workstation-fc01
python catalog.py locate --client workstation-fc01 --task ifs-ens-2025
```

locate 核对挂载和路径可访问性。客户端记录中的核验状态来自相应产品的验收文件或清点结果。verified 表示本机在所述方法下核验，archive_checked 表示核验了归档容器，inventory 表示本机确认文件、目录或文件名范围，sample_checked 表示抽样，registered 表示沿用仓库记录，unmapped 表示尚无可用映射，offline 表示已知盘离线待核验。时间范围写明依据；文件名首尾可能包含缺期。进度表中的数据库完成数单独标注。

更新前先 git pull --ff-only。核对各客户端的同产品、区域、时间和分块，再登记明确分配的任务。进度变更只更新负责客户端的记录。推送遇到非快进时重新取回远端，核对负责人和重叠范围后再合并。运行中的任务或已有远端请求要连同其状态、清单和已验文件一起交接。公开索引使用项目与存储代号，凭据、私有仓库地址、请求 ID、绝对路径和数据保存在本机。
