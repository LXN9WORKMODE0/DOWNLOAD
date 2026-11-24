# 在不同电脑上管理同一批下载

每台电脑克隆本仓库。共享任务以“组名＋起报年”为单位；同一项只由一台设备运行。每台电脑各自配置账户与盘符。

本页的年度任务规则适用于 ECMWF MARS 分组下载。其他产品的任务、储备和续跑入口见[研究数据目录](../catalog/research/README.md)。

## 查找已有文件

在仓库下创建 `.local/`，复制 `catalog/locations.example.json` 为 `.local/locations.json`。填入该机可以访问的绝对目录，未挂载的位置留空。Windows 路径可以使用正斜杠。

| 存储代号 | 映射到的根目录 |
|---|---|
| `ifs-pilot` | 原下载器的输出目录，其下直接有 `full_range/` |
| `predict-prepared` | Predict 的 `data/prepared/`，包含半年拼接包和历史验证包 |
| `forecast-drive` | 原始预报归档盘根目录，其下有 `ecmwf/`、`gefs/` 等。索引来自 2026-10-10 清查，年度覆盖待复核 |

```shell
python catalog.py locate
python catalog.py locate --task hydrodynamics-2024
```

`present` 表示路径可访问，已登记字节数的文件也通过了大小核对。其他返回值为 `unmapped`（未配置）、`missing`（当前位置不可访问）及 `size-mismatch`（大小变化）。GRIB 内容以下载器核验记录为准。不同盘上的独立副本使用不同存储代号；多台机器挂载同一块盘可共用代号，各自映射实际路径。本地映射不随 Git 同步。

## 领取与交接

1. 运行 `git pull --ff-only`，打开 `catalog/tasks.csv`。五组按水动力、流域水文、新能源、天气、海运排列，2024 年优先。每行表示完整年度目标。历史样例有单独状态 `pilot_verified`。
2. 为要处理的行填写客户端代号（如 `workstation-a`）、目标存储代号和 `running`。提交并推送该行。推送成功后再下单；如遇非快进，先取回远端版本并核对同一任务是否已经被领取。本机下载锁只覆盖当前输出目录。
3. 只运行已领取的组和年份。`--root` 或 `-DataRoot` 指向本地映射的输出根。续跑时使用原来的根目录。新设备如要接手续跑，应先确认同一盘可见或已完整复制该任务输出（含配置、批次、核验和日志），再更新任务表的客户端。
4. 对暂停任务登记 `paused`，保留客户端和存储代号。完成年度合并后，执行下面的登记命令，将该组全部所需产品流的 GRIB 与各自的 `verified.json` 匹配。登记命令重复执行会更新同一副本。

```shell
python catalog.py register-year hydrodynamics 2024 ifs-pilot
```

5. 将年度行更新为 `annual_verified`，把任务表和数据索引一起提交、推送。新存储代号应在示例映射和使用说明中登记用途。目录扫描、单次测速和单个产品流完成，都不足以证明多产品流的年度任务完成。

本仓库为公开索引。设备使用自选代号，路径登记到存储根以下。密钥放在各自机器的客户端配置或本地 `.env`。大文件、临时文件和带请求号的运行日志保留在数据盘。
