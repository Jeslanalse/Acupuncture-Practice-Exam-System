# Acupuncture-Practice-Exam-System

针刺手法练习 / 考试系统。桌面端 PySide6 + 本机 FastAPI 服务，HTTPS 通信，SQLite 存储。
当前处于**教师端**开发阶段，学生端后续开发。

## 当前进度

| 模块 | 状态 |
| --- | --- |
| 鉴权与会话（数据库白名单 + HTTPS） | 已完成 |
| 教师端 · 学生页（浏览 / 搜索 / 批量改分） | 已完成 |
| 教师端 · 作业页（新增 / 修改 / 删除 / 状态） | 已完成 |
| 教师端 · 手法页（列表 / 搜索 / 删除） | 已完成；新增待接外部设备 |
| 教师端 · 主页 | 占位 |
| 学生端 | 未开始 |
| 动作采集与打标工具 | 独立脚本，尚未接入主程序 |

## 快速开始

1. 运行 `create_venv.bat`，等虚拟环境与依赖装好，在打开的终端执行：

   ```bash
   python server/main.py
   ```

   首次启动会自动生成 `server/certs/`（本地 HTTPS 证书）和 `server/auth.db`（SQLite）。
2. 另开一个 `create_venv.bat`，在新终端执行：

   ```bash
   python main.py
   ```

3. 测试账号：`admin` / `hitsz`。
4. 示例数据：

   ```bash
   python server/seed_demo.py
   ```

   会为 `admin` 生成 5 名学生（`2023001`–`2023005`，密码同为 `hitsz`）、4 项作业和部分成绩；
   可重复执行，不会重复插入。

## 教师端功能

教师登录后有三个业务页，数据按教师隔离（只能看到自己名下的学生与自己创建的作业、成绩）。

- **学生页**：姓名、学号 + 每个作业一列的成绩。
  - 按姓名或学号搜索，「显示全部」恢复；
  - 支持单格/多格选择、点列头选整列、点行号选整行；
  - 「修改成绩」把选中的成绩批量设为同一个分数（0–100），姓名/学号列不参与修改；
  - 作业列按起始时间正序排列，表头悬停可见作业描述与起止时间。
- **作业页**：列 题目 / 起始时间 / 截止时间 / 标准手法 / 状态 / 描述。
  - 支持新增、修改（双击行也可）、删除；删除二次确认并级联删除成绩；
  - 状态按当前时间实时计算（未开始 / 进行中 / 已截止）并着色；
  - 支持按题目、描述、手法名称搜索。
- **手法页**：展示手法名称、创建时间、创建者、描述；支持搜索、刷新、删除（二次确认，
  被作业引用的手法不允许删除）。**新增手法依赖外部设备采集，本版本不实现**，点击「新增」只给提示。
- **标准手法**：布置作业的下拉框内置「人工批阅」（`technique_id = NULL`），其余选项来自手法列表；
  选择已有手法时会把名称快照进作业，手法以后被删也能正常展示。

## HTTPS

服务端默认只跑 HTTPS。首次启动会**自动生成**本地证书链到 `server/certs/`：

| 文件 | 用途 |
| --- | --- |
| `ca.crt` | 本地 CA，客户端唯一信任锚 |
| `ca.key` | 本地 CA 私钥（仅服务端签发用，勿外传） |
| `server.crt` / `server.key` | 签发给 `127.0.0.1` / `localhost` 的服务器证书与私钥 |

- 客户端 `app/client.py` 用 `server/certs/ca.crt` 做**完整校验**（主机名、有效期、签发链），
  不使用 `verify=False`；默认地址 `https://127.0.0.1:8000/`。
- **先启动服务端生成证书，再启动客户端**；证书缺失时登录会提示「安全连接失败」。
- 证书缺失或 7 天内到期会自动补发；`python server/tls.py --force` 可强制重建整条链
  （客户端会自动读取新的 `ca.crt`，无需改配置）。
- 证书与私钥都在 `.gitignore` 里；跨机器部署请改用正式 CA 签发的证书。

## 鉴权与会话

服务端采用「数据库白名单」：每次登录在 `server/auth.db` 的 `sessions` 表登记一条会话
（只存 JWT 的 `jti`，不存 token 明文），之后每个请求都必须命中一条未撤销、未过期、未空闲超时的记录。

- **主动登出**：立即撤销会话，token 立刻失效。
- **关闭客户端**：主窗口关闭时自动登出；应用退出前还有一层兜底登出。
- **异常退出 / 崩溃**：心跳停止，会话最迟在空闲超时后失效（默认 20 分钟）。
- **重新登录**：默认单会话，新登录会把遗留旧会话标记为 `superseded`，不会叠出多个可用 token。
- **持久化**：会话与撤销状态写入 SQLite，服务重启后依旧生效。

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | `dev-secret-change-me` | JWT 密钥，生产环境必须覆盖 |
| `AUTH_TOKEN_TTL_MINUTES` | `720` | 会话绝对上限（分钟） |
| `AUTH_IDLE_TIMEOUT_MINUTES` | `20` | 空闲超时（分钟），客户端每 5 分钟心跳续期 |
| `AUTH_SINGLE_SESSION` | `1` | 是否单会话 |
| `AUTH_SESSION_RETENTION_DAYS` | `7` | 已失效会话记录的保留天数 |
| `AUTH_DB_PATH` | `server/auth.db` | 数据库文件位置 |
| `AUTH_PORT` | `8000` | 服务端监听端口 |
| `AUTH_TLS` | `1` | 是否启用 HTTPS（`0` 回落明文，仅调试） |
| `AUTH_TLS_DIR` | `server/certs` | 证书目录 |
| `APP_API_BASE` | `https://127.0.0.1:8000/` | 客户端 API 地址（客户端侧） |
| `APP_CA_BUNDLE` | `server/certs/ca.crt` | 客户端信任锚（客户端侧） |

`AUTH_PORT` / `AUTH_TLS` / `AUTH_TLS_DIR` 由 `server/main.py` 读取；其余同样对服务端进程生效。

## 接口

认证（均无需登录，除标注外）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/login` | JSON `{id, password}` → `access_token` |
| POST | `/auth/logout` | 撤销当前会话（幂等） |
| POST | `/auth/logout-all` | 撤销当前用户全部会话 |
| GET | `/auth/me` | 当前用户信息，兼作客户端心跳 |
| GET | `/health` | 探活（无需鉴权） |

教师端（需要教师账号，`teacher` / `admin`）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/teacher/gradebook` | 学生 × 作业成绩矩阵（学生页、作业页共用） |
| GET | `/teacher/assignments` | 作业列表 |
| POST | `/teacher/assignments` | 新增作业 |
| PUT | `/teacher/assignments/{id}` | 修改作业 |
| DELETE | `/teacher/assignments/{id}` | 删除作业（级联成绩） |
| PUT | `/teacher/scores` | 批量改分（`cells` + `score`，`score: null` 表示清空） |
| GET | `/techniques` | 手法列表 |
| DELETE | `/techniques/{id}` | 删除未被作业引用的手法 |
