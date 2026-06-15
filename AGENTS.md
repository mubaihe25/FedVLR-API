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

- `/workbench/options`、`/workbench/validate`、`/workbench/jobs`、`/workbench/jobs?limit=12&page=...`、`/workbench/jobs/{job_id}`、`/workbench/jobs/{job_id}/logs` 和 `/workbench/jobs/{job_id}/result` 是前端攻防工作台的受限联动接口。
- 这些端点包装 `FedVLR/scripts/generate_workbench_smoke_config.py` 和白名单 runner `FedVLR/scripts/run_workbench_smoke_job.py`，只允许写入 `FedVLR/outputs/workbench_jobs/{job_id}`。
- `/workbench/jobs` 可以启动真实全量训练子进程，返回 `queued` / `running` / `completed` / `partial` / `failed`。它不是生产队列，也不能执行前端传来的任意命令。
- 新 job 必须把点击“开始实验”时的 `started_at` 和规范中文 `experiment_name` 写入独立 `metadata.json`；名称格式为 `{推荐操纵|成员推断|更新泄露|聚合防御} · YYYY-MM-DD HH:mm:ss`。runner 后续更新 `status.json` 时不得改变历史页使用的开始时间语义。
- `GET /workbench/jobs?limit=12&page=...` 必须从 `FedVLR/outputs/workbench_jobs` 读取 job 档案，返回 `job_id`、`experiment_name`、`direction`、`dataset`、`model`、`execution_mode`、`source`、`status`、时间戳、`key_metrics` 和相对路径，不暴露本地绝对路径。列表必须排除 job_id 或名称包含 `test`、以 `codex_` 开头、或缺少可解析 `started_at` 的测试/残缺任务；保留任务严格按解析后的 `started_at` 降序排列，不能使用完成时间代替。
- `/workbench/options` 必须保持 canonical：只返回 `AMAZON_BEAUTY_POC`、`KU` 两个启动数据集和 8 个可启动模型，同时返回 `common_parameters`、`fixed_parameters`、`direction_parameters`、`defense_parameters`、`model_dataset_execution`、`parameter_descriptors` 以及目标商品中文展示字段。标签、范围、步长、默认值和动态上限以 FedVLR schema 为唯一来源。运行时性能参数（`num_workers` / `prefetch_factor` / `pin_memory` / `persistent_workers` / `amp_enabled` / `cache_item_features_on_device` / `non_blocking_transfer` / `reuse_client_model_workspace`）已收口为后端固定安全默认值（`num_workers=0, prefetch_factor=None, pin_memory=false, persistent_workers=false, amp_enabled=false, cache_item_features_on_device=true, non_blocking_transfer=true, reuse_client_model_workspace=true`），`/workbench/options` 不再把它们作为 `parameter_descriptors` / `allowed_params` / `defaults` 的一部分返回。
- `/workbench/validate` 和 invalid `/workbench/jobs` 响应应保留 `field_errors`；`error_message` 要合并关键字段错误，方便前端展示启动失败原因。基础 schema 通过后必须调用 FedVLR `.venv` 中的 `scripts/workbench_forward_preflight.py`，真实最小 forward 未通过时不得创建 job。
- `/workbench/validate` 和 `/workbench/jobs` 在字段缺失时默认补 `execution_mode=full_train`；显式提交旧模式必须校验失败，不能静默转换。
- `/workbench/validate` 和 `/workbench/jobs` 的 payload 必须先经过 `coerce_runtime_safety` 收口：8 个运行时性能参数（`num_workers` / `prefetch_factor` / `pin_memory` / `persistent_workers` / `amp_enabled` / `cache_item_features_on_device` / `non_blocking_transfer` / `reuse_client_model_workspace`）一律覆盖为 `WORKBENCH_RUNTIME_SAFE_DEFAULTS`（同时接受驼峰 / 大小写变体），即便旧前端或 curl 显式提交也不会影响训练。
- `/workbench/validate` 和 `/workbench/jobs` 固定 `top_k=50`，不得接受 UI 自定义 TopK。单次最多接受一个鲁棒聚合算法；空数组表示普通 FedAvg 聚合。Krum 校验 `krum_f`、`multi_krum_enabled`、`distance_metric`、`gradient_clip_norm`，Median 校验 `gradient_clip_norm` 和 `outlier_strategy`；`gradient_clip_norm` 与更新扰动层的 `max_grad_norm` 必须保持独立。Krum/Bulyan 的 `f` 与 TrimmedMean 最少保留客户端数必须按本轮采样客户端数动态校验，非法值通过 `field_errors` 返回。更新扰动层参数同样复用 schema descriptor，且不得写成 formal DP。
- 新 job 只允许 `source=full_train`。不支持的方向、模型或数据集组合必须返回明确 `field_errors` / `error_message`，不能读取既有 artifact 或进入 probe 路径。
- `/workbench/jobs/{job_id}` 状态应带回 `experiment_name`、metadata `started_at`、`direction`、`dataset`、`model`、`execution_mode`、`requested_execution_mode` 和 config summary；旧 job 字段只做读取兼容。
- runner 启动后必须回传并持久化 `runner_pid`、训练子进程 `pid`、`subprocess_command`、`python_path`、`cwd`、`return_code`、`started_at` 和 `finished_at`。训练中日志接口要能读取持续追加的 stdout/stderr；非零退出必须保留 `failure_stage`、中文 `error_summary`、完整 `error_detail`、实际 tensor shape 和模型期望 shape。
- `/workbench/jobs/{job_id}` 与 `/result` 必须透传 `progress_detail`、`epoch_metrics`、`gpu_stats` 和 `performance_summary`。进度只能读取真实 `progress.json`；文件尚未出现时返回初始化状态，不得根据时间或轮数伪造百分比。
- `progress_detail` 保留阶段、中文阶段名、epoch/client 计数、完成客户端数、百分比、elapsed、ETA 和更新时间。completed 才归一到 100%；failed 保留失败时百分比和 `failure_phase`。
- `gpu_stats.csv` 或性能遥测缺失只表示遥测不可用，不能改变训练终态。所有新增性能和进度响应继续执行绝对路径清洗。
- `job_id` 必须是安全路径片段，响应不要暴露本地绝对路径或私有运行参数。
- Workbench 模型列表必须保持 MGCN 系列为 adapter-required，直到 FedVLR 侧有真实 trainer/import 验证。
- `/workbench/jobs/{job_id}/result` 必须兼容旧 job，并对新 job 返回 `workbench-result-v2` 的 `training`、`direction_result`、`warnings`、`missing_evidence`、失败阶段和错误。推荐操纵必须原样透传 `baseline_metrics`、`attack_metrics`、两份推荐、两段排名、攻击阶段 Top50 命中与 Jaccard；有独立防御阶段时再透传 `defense_metrics`、`defended_recommendations`、`defended_target_rank`、`defended_top50_hit`、`defense_vs_baseline_jaccard`。无防御时不得补空 defense 字段，也不得把当前 job 与 showcase/V3 或其他 job 拼接。
- 历史 `key_metrics` 必须按方向映射：推荐操纵的 baseline/attack/defended rank、攻击/防御 Top50 命中、两组 Jaccard、最终命中数/率、结果类型和鲁棒聚合器必须保持阶段语义；成员推断映射 AUC/Accuracy，更新泄露映射 Hit@10/20/50，聚合防御映射 defended Recall/NDCG、恢复率和拒绝数。
- 结果、状态和日志响应不得暴露 D 盘绝对路径或 runner 私有命令。商品图片字段保持 `/showcase/images/{datasetId}/{itemId}?size=thumb`，大型明细需保留 total/returned/truncated 语义。
- `partial` 只表示训练完成但方向证据缺失，必须返回具体 `missing_evidence`；普通验证 warning 不得自动降级终态。
- `model_dataset_execution` 必须区分 `construct_verified`、`forward_verified`、`train_verified`、`direction_verified`。构造成功不等于允许训练；API 以当前真实 preflight 结果作为启动门槛，只有真实完成 job 才能提升 train/direction 证据。
- checkpoint 字段在没有明确 strict compatible loader 时必须校验失败，不能静默忽略或加载维度不兼容权重。
