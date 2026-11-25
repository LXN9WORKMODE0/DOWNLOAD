# 定位数据盘与登记 MARS 年度产物

[下载任务总表](tasks/README.md)记录已发出的指令。年度表将 MARS 任务展开为组名与起报年，存储代号让不同机器都能查到同一份数据。

## 查找已有文件

在仓库下创建 `.local/`，复制 `catalog/locations.example.json` 为 `.local/locations.json`。填入该机可以访问的绝对目录，未挂载的位置留空。Windows 路径可以使用正斜杠。

| 存储代号 | 映射到的根目录 |
|---|---|
| `ifs-pilot` | 原下载器的输出目录，其下直接有 `full_range/` |
| `ifs-annual-fc01` | `workstation-fc01` 的 MARS 年度输出根目录，其下直接有 `full_range/` |
| `predict-prepared` | Predict 的 `data/prepared/`，包含半年拼接包和历史验证包 |
| `forecast-drive` | 原始预报归档盘根目录，其下有 `ecmwf/`、`gefs/` 等。索引来自 2026-10-10 清查，年度覆盖待复核 |

```shell
python catalog.py locate
python catalog.py locate --task hydrodynamics-2024
```

`present` 表示路径可访问，已登记字节数的文件也通过了大小核对。其他返回值为 `unmapped`（未配置）、`missing`（当前位置不可访问）及 `size-mismatch`（大小变化）。GRIB 内容以下载器核验记录为准。不同盘上的独立副本使用不同存储代号；多台机器挂载同一块盘可共用代号，各自映射实际路径。本地映射不随 Git 同步。

## 记录年度进展

1. 同步仓库后，按下载指令查找 `catalog/tasks.csv` 中的组和年份。每行是一个年度目标，试取与年度完成分别记录。
2. 执行后填写状态、记录来源设备及目标存储代号。使用同一 ECMWF 账户时串行提交，先核对已有订单、试取批次与缺口。
3. 续跑沿用原 `--root` 或 `-DataRoot`，保留批次、核验回执和日志。在另一台机器查看数据时，把同一存储代号映射到该机可访问的目录。
4. 对暂停任务登记 `paused`，保留客户端和存储代号。完成年度合并后，执行下面的登记命令，将该组全部所需产品流的 GRIB 与各自的 `verified.json` 匹配。登记命令重复执行会更新同一副本。

```shell
python catalog.py register-year hydrodynamics 2024 ifs-annual-fc01
```

5. 将年度行更新为 `annual_verified`，把任务表和数据索引一起提交、推送。新存储代号应在示例映射和使用说明中登记用途。目录扫描、单次测速和单个产品流完成，都不足以证明多产品流的年度任务完成。

本仓库为公开索引。设备使用自选代号，路径登记到存储根以下。密钥放在各自机器的客户端配置或本地 `.env`。大文件、临时文件和带请求号的运行日志保留在数据盘。
