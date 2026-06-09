# FedVLR-API 协作说明

## 仓库定位

`FedVLR-API` 是后端服务仓库，负责接收前端实验配置、生成临时配置、启动 `FedVLR` 子进程、轮询启动状态、扫描历史结果和只读读取 showcase artifacts，并向前端提供 summary/result/csv/showcase 接口。

## 重点目录

- `app/routes`：FastAPI 路由，包括 health、capabilities/schema、实验启动、历史结果和 showcase。
- `app/services`：能力矩阵读取、结果扫描、showcase artifacts 只读扫描、启动器服务和内存 launch registry。
- `app/models`：API 请求/响应 schema。
- `app/core`：环境变量和路径配置。
- `requirements.txt`：后端运行依赖。

## 开发约束

- 不要随意修改前后端 payload 协议。
- 不要破坏 `experiment_key` 生成规则；前端历史页、结果页和 CSV 下载依赖它。
- 不要随意改变 `FedVLR` 路径解析、临时配置写入、子进程启动方式、stdout/stderr 解析和结果扫描规则。
- showcase artifact API 只读读取 `<FEDVLR_ROOT>/outputs/showcase_artifacts` 或 `SHOWCASE_ARTIFACT_ROOT`；不要修改 artifacts、不要运行训练、不要删除 outputs。
- showcase artifact 响应不要暴露本地绝对路径；scenario `path` 保持为面向前端的相对路径。
- artifact 聚合接口缺失文件应返回 `null` 和结构化 warning；单文件 artifact 缺失才返回 404。
- Security Artifact V3 场景位于 `<SHOWCASE_ARTIFACT_ROOT>/amazon_beauty_poc_security_v3` 这类 scenario 目录；V3 panel 缺失时 `/v3/report` 返回 `null` 和 `missing_panel` warning，单 panel 缺失按 404 处理。
- V3 字段语义必须原样保留：不要把 `attack_topk_hit=false`、`evidence_type=mixed_proxy`、`status=configured_only`、`formal_dp_available=false`、SecAgg demo/simulation 或 target manipulation 指标改写成更强的实现结论。
- V3 可以补充 `display_status`、`display_warning`、`display_tags` 这类展示字段，但不要伪造 formal DP、checkpoint score、attack success 或真实生产级安全聚合证据。
- `launch registry` 当前是进程内内存态，服务重启会丢失状态；不要写成生产级持久任务队列。
- 当前 API 不包含数据库、鉴权、生产级任务队列或真实 stop 控制；如需新增，需要单独设计。
- 不要把差分隐私、同态加密、安全聚合写成已正式实现。

## Showcase Notes

- `showcase_store.py` 读取标准 showcase artifacts，也读取 `model_security_capability_matrix` 目录中的 `model_security_capability_matrix.json`、`supported_demos.json`、`unsupported_reasons.json` 和 `recommended_frontend_labels.json`。
- `/showcase/images/{dataset}/{item_id}?size=thumb|full` 只能返回 `FedVLR/datasets/AMAZON_BEAUTY_POC/item_image_manifest.json` 登记过的图片；默认 `size=thumb`，必须优先服务缩略图，保留路径穿越检查，未登记或文件缺失返回 404。
- 推荐项或 target-rank 行如果存在 manifest 登记图片，可以补 `thumbnail_url` 和 `local_image_url`，但不能暴露 D 盘等本地绝对路径。
- `/showcase/scenarios/{scenario_id}/recommendations` 必须支持 `limit` 和 `column`，默认只返回少量展示行、`total_counts` 和 `has_more`，不要返回全量超大推荐列表。
- `/showcase/scenarios/{scenario_id}/report` 对大型 `recommendation_comparison` 使用 preview rows 加 `total_counts`，保持前端展示可用；更长推荐列表由 `/showcase/scenarios/{scenario_id}/recommendations?limit=5|15|50` 按需读取。
- Security Artifact V3 endpoints 包括 `/showcase/scenarios/{scenario_id}/v3/profile`、`runtime`、`curves`、`target-manipulation`、`membership`、`update-leakage`、`aggregation-defense`、`privacy-defense`、`model-support`、`frontend-summary` 和 `/v3/report`。
- `/showcase/scenarios` 对 V3 只返回轻量摘要字段，包括 `has_v3`、`available_panels`、`supported_directions`、各 panel 的 `has_*` 布尔值和 `has_images`；不要为了列表页读取大推荐列表。

## 验证建议

修改 Python 代码后运行：

```powershell
python -m compileall -q app
```

涉及启动链路时，优先使用 validate-only 或 dry-run，不要默认触发耗时训练。

## Workbench API Notes

- `/workbench/options`、`/workbench/validate`、`/workbench/jobs`、`/workbench/jobs/{job_id}`、`/workbench/jobs/{job_id}/logs` 和 `/workbench/jobs/{job_id}/result` 是前端攻防工作台的受限联动接口。
- 这些端点包装 `FedVLR/scripts/generate_workbench_smoke_config.py` 和白名单 runner `FedVLR/scripts/run_workbench_smoke_job.py`，只允许写入 `FedVLR/outputs/workbench_jobs/{job_id}`。
- `/workbench/jobs` 可以启动受限 smoke 子进程，返回 `queued` / `running` / `completed` / `partial` / `failed`。它不是生产队列，也不能执行前端传来的任意命令。
- `/workbench/options` 必须保持 canonical：只返回 `AMAZON_BEAUTY_POC`、`KU` 两个启动数据集和 8 个可启动模型，同时返回 `direction_parameters`、`defense_parameters`、`compatibility_matrix` 以及目标商品的中文展示字段。
- `/workbench/validate` 和 invalid `/workbench/jobs` 响应应保留 `field_errors`；`error_message` 要合并关键字段错误，方便前端展示启动失败原因。
- `source=real_smoke` 只表示 FedVLR 白名单 1 epoch smoke 已执行；它不是长训练或完整 defense benchmark。
- 复用既有 V3 证据时必须返回 `source=existing_artifact`；聚合防御只有 config-only evidence 时可以返回 `partial`，不能伪造成完整 defense benchmark。
- `job_id` 必须是安全路径片段，响应不要暴露本地绝对路径或私有运行参数。
- Workbench 模型列表必须保持 MGCN 系列为 adapter-required，直到 FedVLR 侧有真实 trainer/import 验证。
