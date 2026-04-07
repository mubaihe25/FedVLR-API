# FedVLR-API

`FedVLR-API` 当前是一个最小只读接口层，用来包装 `FedVLR` 训练主仓已经落盘的实验结果文件。

当前阶段只提供：

- 健康检查
- 实验摘要列表
- 单个实验摘要读取
- 单个实验详细结果读取

不提供：

- 训练启动
- 训练停止
- 结果写操作
- 数据库
- 鉴权

## 目录结构

```text
app/
├─ core/
│  └─ settings.py
├─ models/
│  └─ schemas.py
├─ routes/
│  ├─ experiments.py
│  └─ health.py
├─ services/
│  └─ result_store.py
└─ main.py
```

## 环境变量

优先级：

1. `FEDVLR_RESULTS_DIR`
2. `FEDVLR_ROOT`
3. 默认按工作区兄弟目录推断 `../FedVLR/outputs/results`

## 安装与启动

```powershell
cd FedVLR-API
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## 接口

- `GET /health`
- `GET /experiments/summaries`
- `GET /experiments/{experiment_key}/summary`
- `GET /experiments/{experiment_key}/result`

说明：

- `experiment_key` 是基于结果文件相对路径生成的稳定只读键
- 列表接口会返回 `experiment_key`、`file_name`、`relative_path`
- 前端后续可先用 `experiment_key` 作为详情读取主键
