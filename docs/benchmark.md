# 复现水动力组下载测速

2024 年的试验比较单起报和同带数下的扩大批量。2 月取到 +240 小时，12 月取到 +360 小时，各选一次单起报和一次合单。每个请求均包含水动力组九个字段；一个请求结束后才提交下一个。

```powershell
.\run.ps1 plan -Group hydrodynamics -Year 2024
.\run.ps1 check -Group hydrodynamics -Year 2024
.\run.ps1 benchmark -Group hydrodynamics -Year 2024
.\run.ps1 report -Group hydrodynamics -Year 2024
```

使用同一数据根目录可复用核验成功的试取文件。旧轮数据与新轮独立计时时，可通过 `-DataRoot` 指定新的输出目录。这样会重新提交真实请求并占用下载空间。

| 字段 | 如何解释 |
|---|---|
| `list_s`、`list_calls` | 本单为确定可取场数和预计磁带数所花的总时间、目录请求数 |
| `wait_to_active_s` | Web API 提交至观测到 active 状态；轮询未记录时留空 |
| `archive_wait_and_service_s` | 提交至开始传输，含上项及服务端读档、处理等时间 |
| `transfer_s` | 返回文件的传输时间 |
| `seconds_per_cycle` | 目录查询与下载、落盘、核验的总时长，除以起报次数 |

四笔历史订单共 18 次起报、10,206 场。2 月合单每起报节省 46.544 秒，12 月合单每起报增加 27.218 秒。两次合单均取 8 个起报，目录均为 0 带。2 月首个单起报在修正 GRIB1 累计字段端点核验后复用已下载的数据，其总时长包含复核，原排队和传输的单独计时缺失。每个条件只有一次观测。逐单原始指标见[实测结果](../benchmarks/hydrodynamics-2024.json)。

发布版先查询合单，若场数合理且全部在线便直接取数。历史结果记录的是调整前的请求顺序。比较新旧版本时，应同时报告实际批量、查询时间、总时长和当前磁带数。
