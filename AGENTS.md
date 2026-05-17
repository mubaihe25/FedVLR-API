# FedVLR-API 协作说明

## 仓库定位

`FedVLR-API` 是后端服务仓库，负责接收前端实验配置、生成临时配置、启动 `FedVLR` 子进程、轮询启动状态、扫描历史结果和 showcase artifacts，并向前端提供 summary/result/csv/showcase 读取接口。

## 重点目录

- `app/routes`：FastAPI 路由，包括健康检查、capabilities/schema、实验启动、历史结果和 showcase。
- `app/services`：能力矩阵读取、结果扫描、showcase artifacts 只读扫描、启动器服务和内存态 launch registry。
- `app/models`：API 响应和请求 schema。
- `app/core`：环境变量和路径配置。
- `requirements.txt`：后端运行依赖。

## 开发约束

- 不要随意修改前后端 payload 协议。
- 不要破坏 `experiment_key` 生成规则；前端历史页、结果页和 CSV 下载依赖它。
- 不要随意改变 `FedVLR` 路径解析、临时配置写入、子进程启动方式、stdout/stderr 解析和结果扫描规则。
- showcase artifact API 只读读取 `<FEDVLR_ROOT>/outputs/showcase_artifacts` 或 `SHOWCASE_ARTIFACT_ROOT`；不要修改 artifacts、不要运行训练、不要删除 outputs。
- showcase artifact 响应不要暴露本地绝对路径；scenario `path` 保持为面向前端的相对路径。
- artifact 聚合接口缺失文件应返回 `null` 和结构化 warning；单文件 artifact 缺失才返回 404。
- `launch registry` 当前是进程内存态，服务重启会丢失状态；不要误写成生产级持久任务队列。
- 当前 API 不包含数据库、鉴权、生产级任务队列或真实 stop 控制；如需新增，需要单独设计。
- 不要把差分隐私、同态加密、安全聚合写成已正式实现。

## 验证建议

修改 Python 代码后运行：

```powershell
python -m compileall -q app
```

涉及启动链路时，优先使用 validate-only 或 dry-run，不要默认触发耗时训练。
