# 前人项目分析结论

> 分析对象：`D:\Repository\Acupuncture-Practice-Exam-System`，当前 `main` 分支 HEAD = `8105a41`（提交信息「更新Quick Start」）。
> 分析方式：逐文件通读 + 离屏（`QT_QPA_PLATFORM=offscreen`）实机启动验证 + 真实启动 FastAPI 服务做接口联调。
> 一句话结论：**目前实现的是一个「能登录、能进主界面骨架」的可运行最小闭环，外加一个未接入主程序的独立手势采集打标工具；仓库名里的「考试」业务（题库、手法练习、评分、成绩）尚未开始实现。**
>
> 当前状态（2026-10-17）：教师端「学生 / 作业 / 手法」页已实现（§11），鉴权已重构为数据库白名单（§9），
> 全链路 HTTPS（§10），服务端启动入口拆分到 `server/main.py`（§12），README 已同步更新。

---

## 1. 项目概况

| 项目 | 内容 |
| --- | --- |
| 仓库名 | `Acupuncture-Practice-Exam-System`（针刺手法练习考试系统） |
| 界面标题 | 「针刺手法规范系统」 |
| 形态 | 桌面端 PySide6 GUI + 本机 FastAPI HTTPS 服务（C/S 分离，全部跑在 127.0.0.1） |
| 版本来源 | 克隆自 `https://github.com/Jeslanalse/Acupuncture-Practice-Exam-System.git`，本地两个提交：`d7fd3dd` 登录窗口和基本的主界面 → `8105a41` 更新Quick Start |
| 代码规模 | 分析时：手写 Python 852 行 + uic 生成 137 行；现状（2026-10-17）：手写约 2385 行 + uic 生成 511 行（服务端 7 个模块、客户端 10 个模块，独立工具 548 行不计） |
| 实际依赖版本（取自 `.venv`） | Python 3.11.9、PySide6 6.12.0、FastAPI 0.143.0、Starlette 1.7.0、Pydantic 2.14.1、PyJWT 2.15.1、bcrypt 5.0.0、requests 2.34.2、uvicorn 0.54.0；另装有 PyQt5 5.15.11（仅独立工具使用，未写进 `requirements.txt`） |

### 文件清单

| 路径 | 作用 | 备注 |
| --- | --- | --- |
| `main.py` | 程序入口 + `AppController` | 负责登录窗口 ↔ 主窗口的切换与销毁 |
| `app/client.py` | HTTP 客户端封装 | 全项目唯一与后端通信的层，持有 token |
| `app/login.py` / `app/login.ui` / `app/ui_login.py` | 登录窗口 | `.ui` 是源文件，`ui_login.py` 由 `uic.bat` 生成 |
| `app/mainwindow.py` / `app/mainwindow.ui` / `app/ui_mainwindow.py` | 主窗口 | 分析时为 3 个空 Tab；现为 主页/手法/学生/作业，后三页已实现（§11） |
| `server/auth.py` | FastAPI app 组装 + 认证接口 | 分析时为内存用户库 + 黑名单；现为 SQLite 白名单（§9），且不再负责启动（§12） |
| `server/main.py` | 服务端启动入口 | uvicorn + HTTPS/端口/证书；2026-10-17 从 `auth.py` 拆出（§12） |
| `standalone_interaction_collector.py` | 独立动作交互采集与打标工具 | PyQt5 编写，独立进程运行，已随提交入库、文件属性为只读 |
| `create_venv.bat` | 一键建环境 | 强依赖 Python 3.11 |
| `uic.bat` | 由 `.ui` 重新生成 `ui_*.py` | 四条 `pyside6-uic` 命令（含作业/成绩对话框） |
| `requirements.txt` | 8 项依赖（含 `cryptography`） | 仍缺 PyQt5（独立工具用） |
| `README.md` | 快速开始 + 进度/功能/接口说明 | 已按现状更新；历史命令问题见 §6-7 |
| `.gitignore` | 忽略 `.venv`、`__pycache__`、`server/*.db*`、`server/certs/` | — |

> 上表按分析当时的工作区整理并已标注现状。后续迭代还新增了 `server/security.py`、`server/teacher.py`、
> `server/db.py`、`server/tls.py`、`server/seed_demo.py`，以及 `app/student_page.py`、`app/assignment_page.py`、
> `app/technique_page.py`、`app/assignment_dialog.py`、`app/score_edit_dialog.py`、`app/helpers.py`，
> 职责见 §9–§12。

---

## 2. 已实现功能（逐模块）

> 本节 2.2–2.4 记录分析当时的实现与界面参数（如 900×600、HTTP、三个空 Tab）；
> 后续迭代见 §9–§12，其中界面已改为布局装配、主窗口 1200×720。

### 2.1 服务端：本地鉴权服务（功能完整、可独立运行）

> 注意：本节记录的是分析时的旧实现（内存黑名单 + 内存用户库）。该部分随后已重构为
> 「数据库白名单 + 空闲超时 + 客户端关闭自动登出」，差异与验证见 §9。

启动（旧入口）：`.venv\Scripts\python.exe server\auth.py` → uvicorn 监听 `127.0.0.1:8000`，应用标题 `Auth Test Server`，OpenAPI 3.1.0 文档在 `/docs`。启动逻辑现已拆到 `server/main.py`，见 §12。

| 方法 | 路径 | 鉴权 | 请求体 | 成功 | 失败 |
| --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | — | JSON `{"id", "password"}` | `200 {"access_token": "...", "token_type": "bearer"}` | `401 账号或密码错误`、`422` 字段缺失 |
| POST | `/auth/logout` | Bearer | — | `200 {"message": "已登出"}` | `401` |
| GET | `/auth/me` | Bearer | — | `200 {"id": "<用户名>"}` | `401 Not authenticated` / `Invalid token` / `Token has been revoked` |

实现细节：

- **密码哈希**：`bcrypt` 加盐（`hash_password` / `verify_password`），密码不以明文保存。
- **令牌**：JWT，`HS256`，payload 为 `{sub, exp}`，有效期 60 分钟（`ACCESS_TOKEN_EXPIRE_MINUTES`）。
- **登出即失效**：`_TOKEN_BLACKLIST` 内存集合，`get_current_user` 先查黑名单再解码，登出后原 token 立刻返回 401。
- **用户库**：内存字典，导入时预置 `admin` / `hitsz`（每次启动用 bcrypt 现场生成哈希）。
- **安全习惯**：登录失败统一提示「账号或密码错误」，不泄露用户是否存在。
- **并发模型**：三个端点都是同步 `def`，由 FastAPI 线程池执行，bcrypt 计算不阻塞事件循环。

### 2.2 桌面客户端：登录 ↔ 主界面完整闭环（已跑通）

**会话控制（`main.py`）**

- 全局只建一个 `Client` 实例，token 在窗口切换间复用。
- `Login.login_success` 信号 → 销毁登录窗口（`deleteLater`）→ 创建主窗口。
- `MainWindow.logout` 信号 → 销毁主窗口 → 重新创建空白登录窗口（token 已置空）。
- 由 `QApplication` 事件循环驱动，`sys.exit(app.exec())` 正常退出。

**通信层（`app/client.py`）**

- `URL_BASE = "http://127.0.0.1:8000/"`，统一 `_request()` 注入 `Authorization: Bearer <token>`。
- 三个业务方法：`login(id, password)`、`logout()`、`get_user_id()`。
- 所有 `requests` 异常被捕获后 `print` 并返回 `False` / `None` / `"未知用户"`（静默降级）。

**登录窗口（400×300）**

- 账号 / 密码输入框（密码掩码、自带清除按钮）、Tab 键顺序 `account → password → btnLogin`。
- 账号框回车 → 焦点跳到密码框；密码框回车 → 直接提交。
- 提交时禁用输入框与按钮，防止重复请求；失败后恢复并红字提示；任一输入变化即清空提示；启动时焦点在账号框。
- 空账号/空密码 → 前端拦截提示「请输入账号和密码」。

**主窗口（900×600）**

- `QTabWidget` 左侧（West）竖排三个 Tab：**主页 / 手法 / 学生成绩** —— 三个页面均为**空白 QWidget**（实测每页子控件数为 0）。
- 顶部问候标签：静态拼接「早上好、中午好、晚上好！{用户名}」，用户名来自额外一次 `/auth/me` 请求。
- 右上「退出登录」按钮：禁用自身 → 调用服务端登出 → 发信号回登录页。

**UI 工程链路**：`app/*.ui` 为可维护源文件，`uic.bat` 用 `pyside6-uic` 生成 `ui_login.py` / `ui_mainwindow.py`；生成文件头注明 Qt uic 6.12.0，不应手改。

### 2.3 独立工具：动作交互采集与打标（能独立跑，未接入主程序）

定位（文件头注释明确）：**无需肌电手环**，只按「基态 → 目标 → 基态」(B→T→B) 节奏给受试者做动作提示，同时保存自动阶段标签和人工标记；不连接、不读取、不模拟 EMG 数据。仅依赖 PyQt5。

- **手势集（10 个，缺 G8）**：`R0` 静息态、`G1` 张手、`G2` 握拳、`G3` 八、`G4` 竖大拇指、`G5` 指向、`G6` V 手势、`G7` 指尖捏、`G9` 四、`G10` 六。
- **实验组（4 组）**：

| 组 | 含义 | 基态 | 目标动作数 | 静态组 |
| --- | --- | --- | --- | --- |
| B01 | 静息态为基态 | R0 | 9（G1–G7、G9、G10） | 是 |
| B02 | 张手为基态 | G1 | 8 | 否 |
| B03 | 握拳为基态 | G2 | 5（G3、G4、G5、G6、G10） | 否 |
| B04 | 八为基态 | G3 | 3（G4、G5、G7） | 否 |

- **协议节奏**：准备（默认 2 s，可设 0.5–10 s）→ 形成/转换 2 s → 维持目标 3 s → 回落/转换 2 s → 维持基态 2 s；开头有 2 s 静息保持；基态非 R0 时，开头额外「2 s 形成基态 + 3 s 维持」，结尾额外「2 s 放松 + 3 s 静息」。每目标可重复 1–20 次，可勾选随机目标顺序。
- **阶段数与总时长**（实测 `reps=2`、准备 2 s）：B01 = 92 段 / 202 s，B02 = 88 段 / 194 s，B03 = 58 段 / 128 s，B04 = 38 段 / 84 s。
- **界面能力**：
  - 阶段徽标（执行准备 / 执行 / 维持 / 恢复，按相位配色）+ 剩余秒数倒计时 + 当前动作指令 + 「当前是第几次动作」说明。
  - B→T→B 时间轴：三张姿态图分别停在执行准备/执行/恢复起点，下方相位色带 + 实时进度游标。
  - 协议总进度条（千分制映射为百分比）+ 阶段计数。
  - 开始协议 / 暂停（可继续，暂停期间计时冻结并从断点恢复）/ 停止并保存。
  - 人工补充标记：观察备注 / 有效 / 无效或误动作 / 需重做 / 自定义 + 自由备注，立即追加到事件 CSV。
  - 协议运行中锁定配置项；关闭窗口时若协议未结束，弹窗确认「是否停止并保存」。
- **输出产物**：
  - `<session>_events.csv`，13 列：`event_type, timestamp_local, elapsed_s, session_id, group_id, phase, gesture_from, gesture_to, base_gesture, target_gesture, cycle_index, planned_duration_s, note`；事件类型 `protocol_start / step_start / step_end / protocol_pause / protocol_resume / protocol_stop / protocol_complete / manual_marker`；每写一行立即 flush。
  - `<session>_metadata.json`：`schema_version: 1`、`data_source: manual_interaction_only`、`completed`、`session_id`、`subject_id`、`group`（title/base/targets/static_group）、`protocol_parameters`（准备时长/重复次数/是否随机）、`gesture_definitions`、`event_count`、`created_at`、`note`；开始时先写 `completed=false`，结束时覆盖为真实结果。
- **会话命名**：`<受试者号>_<组号>_<YYYYmmdd_HHMMSS>`，受试者号会清洗非法字符并截断 32 字符；输出目录默认 `<仓库>/interaction_labels`，可在界面另选。
- **姿态图**：从 `gesture_assets/hand_gesture_sheet.png` 按 4×3 网格裁切显示；**该资源当前不存在**，实测降级为「未找到手势图片」。

### 2.4 工程脚手架

- `create_venv.bat`：自动定位 Python 3.11（`py -3.11` 或 `python3.11`），建 `.venv`、激活、安装 `requirements.txt`，最后 `call cmd` 留在已激活的 shell 里。
- `uic.bat`：`pyside6-uic app\login.ui` / `app\mainwindow.ui` 重新生成界面代码。
- `README.md`：两步启动 + 测试账号。
- `.gitignore`：排除 `.venv` 与 `__pycache__`。

---

## 3. 架构与数据流

```
PySide6 桌面端（单进程）
  main.py : AppController
    Login ──login_success──▶ MainWindow ──logout──▶ Login（重建）
    MainWindow：QTabWidget(WEST) → 主页 / 手法 / 学生 / 作业（后三页已实现，见 §11）
    Client(token)：requests + Authorization: Bearer，HTTPS + 本地 CA 校验
        │
        │  HTTPS  127.0.0.1:8000
        ▼
服务端（server/main.py 启动 uvicorn，server/auth.py 组装 app）
  /auth/*      → bcrypt + JWT + SQLite 白名单会话（§9）
  /teacher/*   → 成绩册 / 作业 / 批量改分，按教师隔离（§11）
  /techniques  → 手法列表 / 删除
  SQLite（server/auth.db）：users / sessions / techniques / assignments / scores

独立进程（与上述两者无任何调用关系）
  standalone_interaction_collector.py（PyQt5，无网络调用）
    协议引擎 build_steps → 提示界面 + 计时 → events.csv / metadata.json
```

**token 生命周期**：登录成功 → 存入 `Client.token` → 每个请求自动带 `Authorization` → 登出时服务端拉黑、客户端置 `None` → 回登录页。全程不落盘、不写本地存储。

---

## 4. 未实现 / 纯占位部分

> 以下为分析当时的空白状态。教师端学生/作业/手法页已于 §11 落地，学生端仍未开始。

- **主窗口三个 Tab 全空**：没有题库、没有针刺手法演示/练习/评分、没有学生成绩与历史记录页面。
- **没有任何「考试」业务逻辑**：无题目模型、无答题流程、无评分规则、无成绩单、无考试会话管理；现有动作是通用手势，不含进针、捻转、提插等针刺手法定义。
- **无持久化**：用户、成绩、会话均在内存或 CSV/JSON 文件；无数据库、无 ORM、无迁移。
- **无角色与账号体系**：无学生/教师区分、无注册、无改密、无权限分级。
- **主程序与采集工具零集成**：主程序不能启动采集工具、不能读取其 CSV、不能把动作标签关联到练习或成绩。
- **无工程保障**：无单元测试、无 CI、无日志框架、无配置文件/环境变量管理。
- **无资源与文档**：缺少手势图片资源；无接口文档以外的设计说明。

---

## 5. 本次实测记录（用于佐证上文结论）

环境：`.venv` Python 3.11.9；服务端以 `.venv\Scripts\python.exe server/main.py` 真实启动（拆分前为 `server/auth.py`，两者等价，见 §12）；GUI 以 `QT_QPA_PLATFORM=offscreen` 离屏构建。

**接口联调**

| 场景 | 实测结果 |
| --- | --- |
| `admin` / 错误密码 | 401 `{"detail":"账号或密码错误"}` |
| 不存在的用户 | 401 同上（不泄露用户是否存在） |
| 缺 `password` 字段 | 422 `Field required` |
| `admin` / `hitsz` | 200，返回 `access_token` 与 `token_type: bearer` |
| 带 token `GET /auth/me` | 200 `{"id":"admin"}` |
| 不带 token | 401 `Not authenticated` |
| 伪造 token | 401 `Invalid token` |
| `POST /auth/logout` | 200 `{"message":"已登出"}` |
| 登出后复用同一 token | 401 `Token has been revoked`（黑名单生效） |

**客户端生命周期**

| 场景 | 实测结果 |
| --- | --- |
| 空账号提交 | 提示「请输入账号和密码」，按钮恢复可用 |
| 错误密码 | 提示「账号或密码错误」，token 不回填，输入框恢复可用 |
| 正确登录 | token 写入 `Client`，`get_user_id()` 返回 `admin` |
| 登录成功 | 登录窗口销毁，主窗口创建；标题「针刺手法规范系统」，三个 Tab「主页/手法/学生成绩」，Tab 在左侧，问候语含 `admin`；每页子控件数 0（确认是空占位） |
| 退出登录 | 服务端登出成功、`logout` 信号触发、token 变 `None`、主窗口销毁、登录窗口重建、按钮已禁用 |
| 服务未启动 | `login()` 返回 `False`、`get_user_id()` 返回「未知用户」，但界面提示仍是「账号或密码错误」 |

**采集工具**

| 场景 | 实测结果 |
| --- | --- |
| 四组协议构建（reps=2） | 段数/时长：B01 92/202 s、B02 88/194 s、B03 58/128 s、B04 38/84 s |
| 随机目标顺序 | 每个目标出现次数仍严格等于重复次数（守恒校验通过） |
| 窗口默认值 | 受试者 `S01`、重复 1、准备 2.0 s、不随机、输出目录 `<仓库>/interaction_labels` |
| 空闲态按钮 | 开始可用；暂停/停止/人工标记禁用 |
| 缺失姿态图 | 显示「未找到手势图片」 |
| 模拟一次完整 B02 会话（跳过实时等待，直接推进阶段） | 48 阶段会话落盘 `..._events.csv`（本次 52 行：表头 + `protocol_start` + 1 条 `step_start` + 48 条 `step_end` + `protocol_complete`）与 `..._metadata.json`（`completed: true`、`event_count` 正确）；真实运行时每个阶段还会各写一条 `step_start`，行数接近翻倍 |

说明：计时与暂停/继续逻辑通过读代码 + 驱动刷新函数验证，未真实等待 200 秒跑完整个协议，也未做长时间计漂移测量。

---

## 6. 问题与风险

> 本章为分析当时的问题清单。已解决项：§9（会话/安全相关）、§10（HTTPS 明文传输）、
> §11（学生/作业/手法页与布局装配）、§12（启动入口与 README 命令）；未解决项仍按原样保留。

| # | 等级 | 问题 | 证据 | 影响 |
| --- | --- | --- | --- | --- |
| 1 | 高 | 考试核心业务完全缺失 | 三个 Tab 页面无任何子控件；全仓库无题目/成绩/评分代码 | 项目名与实现严重不符，当前不具备任何「练习考试」价值 |
| 2 | 高 | 网络请求在 GUI 线程同步执行且未设超时 | `client.py` 直接 `requests.request(...)`，无 `timeout`；`login.py` 在按钮槽里同步调用 | 服务未启动或网络卡住时界面冻结，最长无限等待，用户只能强杀 |
| 3 | 高 | 安全配置薄弱 | `SECRET_KEY = "dev-secret-change-me"` 硬编码；用户库/黑名单均在内存；HTTP 明文传输口令；测试口令 `admin/hitsz` | 密钥泄露即可伪造任意用户令牌；服务重启后已登出的 token 会「复活」（黑名单清空而密钥不变）；口令明文过网 |
| 4 | 中 | OAuth2 声明与实际协议不一致 | `OAuth2PasswordBearer(tokenUrl="/auth/login")` 期望表单 `username/password`，实际端点是 JSON `{id, password}` | `/docs` 的 Authorize 流程走不通，第三方按标准接入会 422 |
| 5 | 中 | 错误语义混淆、失败仅打印控制台 | 实测服务未启动时界面仍提示「账号或密码错误」；`client.py` 用 `print` 记录异常 | 用户与开发者都难以区分「断网 / 服务没开 / 密码错」，排障成本高 |
| 6 | 中 | 依赖与资源不完整 | `requirements.txt` 无 PyQt5，但采集工具 `import PyQt5`（本机恰好已装）；`gesture_assets/hand_gesture_sheet.png` 缺失 | 新机器按 `requirements.txt` 装完仍跑不了采集工具；姿态图全部降级为文字 |
| 7 | 中 | README 启动命令在本项目 venv 下不可用 | 在激活的 `.venv` 里执行 `py -3.11 -c "import PySide6"` 报 `ModuleNotFoundError`（Windows `py` 启动器不继承 venv） | 照 README 操作新人直接卡在第一步，实际应使用 `python main.py` |
| 8 | 中 | 界面全绝对定位、固定尺寸、不居中 | 两个 `.ui` 全为 `geometry` 坐标，无 layout；登录 400×300、主窗 900×600 | 无法缩放、高 DPI 或换字体即错位；主窗退出按钮坐标写死 |
| 9 | 低 | 双 Qt 绑定并存 | 主程序 PySide6 6.12，工具 PyQt5 5.15 | 未来若合并进程会冲突，需先统一绑定 |
| 10 | 低 | 主窗口问候语造假象 | `"早上好、中午好、晚上好！"` 是静态字符串，不判断时段 | 内容无意义；且进入主窗口多打一次 `/auth/me` |
| 11 | 低 | 服务端细节不严 | `/auth/logout` 不校验 token 合法性就拉黑；无注册/改密/限流；JWT 无 `iat`/`jti`/刷新机制 | 无法做账号生命周期管理与防爆破 |
| 12 | 低 | 采集工具覆盖面有限 | 单次单被试；无 G8；4×3 图集与 10 个手势不匹配；时间戳为本地时间无时区；文件名含受试者编号 | 多被试需反复手工操作；数据可追溯性弱、有隐私隐患 |

---

## 7. 建议的后续优先级

> 以下是分析当时的建议清单。其中「主页、手法、学生成绩」三页的落地方案已由 §11 的
> 「学生」「作业」「手法」页实现替代；启动入口与 README 的整理已在 §12 完成。

1. **P0 业务定盘**：明确考试范围（手法条目、操作流程、评分维度与分值、合格线），先产出数据模型（学生 / 题目 / 考试会话 / 评分项 / 成绩），再把「主页、手法、学生成绩」三个空页落地。
2. **P1 通信层改造**：所有请求加 `timeout`，改 `QThread`/`QNetworkAccessManager` 异步执行；错误分类为「服务不可用 / 凭据错误 / 服务端异常」并给出可操作提示；补加载态。
3. **P2 安全与持久化**：`SECRET_KEY` 走环境变量；引入 SQLite 持久化用户与成绩，黑名单持久化或用可撤销 token；统一 OAuth2 表单语义或改用 `HTTPBearer`；补注册/改密/限流。
4. **P3 界面工程化**：`.ui` 改 layout、自适应与居中；统一 Qt 绑定（建议把采集工具从 PyQt5 迁到 PySide6）；补 `gesture_assets` 并在 `requirements.txt` 落实依赖。
5. **P4 打通与保障**：采集工具产出的标签能与考试/练习记录关联（成绩可回溯原始动作数据）；补单元测试（鉴权、协议构建、CSV schema）与日志。

---

## 8. 附录：关键常量与字段速查

**服务端**：`SECRET_KEY`（默认 `dev-secret-change-me`，可用 `AUTH_SECRET_KEY` 覆盖）、`ALGORITHM="HS256"`、会话绝对上限 720 分钟、空闲超时 20 分钟、预置用户 `admin/hitsz`、默认监听 `https://127.0.0.1:8000`。

**客户端**：`URL_BASE="https://127.0.0.1:8000/"`（用本地 CA 校验）；登录窗口 400×300；主窗口 1200×720（最小 1000×640）；Tab 位置 West。

**采集工具**：10 个手势、4 个实验组、准备好 0.5–10 s、重复 1–20 次、定时器 50 ms、会话文件 `<subject>_<group>_<timestamp>`、默认输出目录 `<仓库>/interaction_labels`、事件 CSV 13 列、元数据 `schema_version=1` / `data_source=manual_interaction_only`。

---

## 9. 后续迭代：鉴权与会话重构（2026-10-17）

### 9.1 旧实现的问题

- 用户库与 token 黑名单都在内存：服务一重启，已登出的 token 立刻「复活」，用户数据也丢失。
- 登录后**直接关闭 app、不点退出登录**：服务端完全无感知，token 仍能用满 60 分钟；
  反复开关程序会叠加出多个同时有效的 token，且无法在服务端收口。
- 缺少「登出全部会话」、会话元数据与审计；`OAuth2PasswordBearer` 声明（表单）与实际 JSON 登录不一致。
- bcrypt 5.x 对超过 72 字节的密码会抛 `ValueError`，旧代码会直接 500。

### 9.2 新方案：SQLite 白名单会话

| 维度 | 旧实现 | 新实现 |
| --- | --- | --- |
| 用户库 | 内存字典 | `users` 表（bcrypt 哈希，首次启动预置 `admin/hitsz`） |
| 撤销机制 | 内存 `set` 黑名单 | `sessions` 白名单表，**只存 `jti`，不存 token 明文** |
| 校验条件 | 只验 JWT 签名与 `exp` | JWT 合法 + 会话存在 + 未撤销 + 未到绝对上限 + 未空闲超时 |
| 失效时效 | 固定 60 分钟 | 绝对上限默认 12 小时（仅兜底）+ 空闲超时默认 20 分钟（心跳续期）+ 主动登出 |
| 登出 | 任何 token 直接塞黑名单 | 幂等撤销；token 已过期/已撤销也返回 200，避免关窗时报错 |
| 多会话 | 每次登录各自有效 | 默认单会话，新登录把旧会话标记 `superseded` |
| 重启后 | 撤销状态丢失 | 会话与撤销状态持久化在 `server/auth.db` |
| 清理 | 无 | 启动与登录时清理超过保留期（默认 7 天）的记录 |
| 安全细节 | 密钥硬编码、超长密码 500 | 密钥可用 `AUTH_SECRET_KEY` 覆盖；401 带 `WWW-Authenticate`；超长密码按凭据错误处理 |

接口变化：新增 `POST /auth/logout-all`；`GET /auth/me` 追加 `issued_at / expires_at / expires_in`；
认证依赖由 `OAuth2PasswordBearer` 改为 `HTTPBearer`（与 JSON 登录一致，`/docs` 的 Authorize 现在可用）。

### 9.3 「登录后未登出直接关闭 app」的处理链路

1. **正常关窗**：主窗口 `closeEvent` 立即调用登出 → 服务端会话 `revoked`，旧 token 立刻 401。
2. **应用退出兜底**：`app.aboutToQuit` → `AppController.shutdown()` 再补一次登出。
3. **进程被杀 / 崩溃**：心跳停止，会话在空闲超时（默认 20 分钟）后被服务端判失效。
4. **重新登录**：单会话策略把遗留会话标记 `superseded`，旧 token 即刻作废，不留可用悬挂凭据。
5. **表膨胀**：失效记录按保留期自动清理。

客户端配套：所有请求带超时（普通 5 s、登出 2 s）；`last_status` 区分「服务未启动」与「登录态失效」；
主窗口每 5 分钟心跳续期；心跳遇 401 自动回到登录页并提示「登录状态已失效，请重新登录」。

### 9.4 本次实测（42 项断言全部通过）

- 白名单：登录 200、`/auth/me` 200、登出 200 且 `revoked=true`、登出后 401 `Token has been revoked`、重复登出仍 200。
- 持久化：重启服务后有效会话仍 200；重启后已撤销会话仍 401（旧黑名单会丢失）。
- 空闲超时：短配置下空闲 4 s 后 401 `Session expired (idle)`，且 `revoked_reason='idle_timeout'` 落库。
- 绝对上限：短 TTL 下 4 s 后 401 `Token expired`；过期 token 登出按幂等 200。
- 单会话：第二次登录后旧 token 401 `Token has been revoked`，新 token 200。
- 表内容：会话行只有 32 位 `jti`，无 `eyJ` 开头的 token 明文。
- GUI：关闭主窗口后本地 token 清空、服务端会话 401；心跳发现失效 → 自动回登录页并显示提示；`shutdown()` 兜底登出生效。
- 错误语义：服务未启动时登录提示「无法连接服务器，请确认服务已启动」，与「账号或密码错误」区分。

### 9.5 配置项（环境变量）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `AUTH_SECRET_KEY` | `dev-secret-change-me` | JWT 密钥，生产必须覆盖 |
| `AUTH_TOKEN_TTL_MINUTES` | `720` | 会话绝对上限（分钟） |
| `AUTH_IDLE_TIMEOUT_MINUTES` | `20` | 空闲超时（分钟） |
| `AUTH_SINGLE_SESSION` | `1` | 是否单会话 |
| `AUTH_SESSION_RETENTION_DAYS` | `7` | 失效记录保留天数 |
| `AUTH_DB_PATH` | `server/auth.db` | 数据库文件（已加入 `.gitignore`） |
| `AUTH_PORT` | `8000` | 监听端口 |

### 9.6 仍未覆盖

- 登录频率限制 / 防爆破；注册、改密、师生角色与权限的实际落地。
- HTTPS（已在 §10 完成）。
- 会话管理界面（列出并踢出设备）。

> 本节取代 §2.1 中关于黑名单、内存用户库与 60 分钟固定有效期的描述，以及 §6 第 3、11 条中
> 与之相关的部分。

---

## 10. 传输加密：全链路 HTTPS（2026-10-17）

### 10.1 方案

- **服务端只跑 HTTPS**：uvicorn 加载本地证书；仅当显式设置 `AUTH_TLS=0` 时才回落明文（调试用）。
- **首启自动生成证书链**（`server/certs/`）：
  - `ca.crt` / `ca.key`：本地 CA（10 年），是客户端唯一的信任锚；
  - `server.crt` / `server.key`：签发给 `127.0.0.1`（SAN 含 IP `127.0.0.1` 与 DNS `localhost`），有效期 825 天。
- **客户端严格校验**：默认地址 `https://127.0.0.1:8000/`，用 `server/certs/ca.crt` 做完整校验
  （主机名、有效期、签发链），代码里**不存在** `verify=False`；可用 `APP_CA_BUNDLE` 指定其他信任锚。
- **证书维护**：缺失或 7 天内到期自动补发；CA 仍有效时只补发叶子证书（客户端信任文件不用换）；
  `python server/tls.py --force` 强制重建整条链。
- **不进版本库**：证书与私钥都在 `.gitignore`；跨机部署请替换为正式 CA 签发证书。

### 10.2 本次实测（30 项断言全部通过）

- 证书：SAN 含 `127.0.0.1` / `localhost`、CA 与叶子基本约束正确、签发关系正确、未过期；
  重复调用不重建；删掉叶子会用同一 CA 补发；`--force` 才会重建 CA。
- 连接：`https://127.0.0.1:8000/health` 200；明文 HTTP 打 TLS 端口被拒；用系统信任锚验证自签证书失败（证明没有放宽校验）；
  HTTPS 下登录 / `/auth/me` / 登出均正常。
- 客户端：默认 CA 校验登录成功、心跳正常；CA 缺失与错误信任锚都被识别为 TLS 问题并给出专门提示，不会静默降级。
- GUI：HTTPS 下登录进入主窗口、心跳运行、关窗后服务端会话撤销、本地 token 清空。
- 回落：`AUTH_TLS=0` 时 HTTP 可用（仅限本机调试）。

### 10.3 局限与边界

- 自签 CA 的信任来自本地文件而非公共 PKI，只适合单机部署；多机/多用户请用正式证书。
- 本机回环上 TLS 的收益主要是防本机被动嗅探、统一安全基线，不能替代服务端权限控制与审计。
- 服务只开 HTTPS 端口，不存在明文入口，因此未做 HTTP→HTTPS 重定向。

> 本节解决了 §6 第 3 条中「HTTP 明文传输口令」的问题；§6 第 3 条其余内容（硬编码密钥、
> 测试口令）仍按 §9 的建议继续收敛。

---

## 11. 教师端「学生」「作业」页面落地（2026-10-17）

### 11.1 服务端

- `server/main.py`：服务端启动入口（uvicorn、HTTPS 证书、端口），2026-10-17 从 `auth.py` 拆出，详见 §12。
- `server/db.py`：新增 `techniques` / `assignments` / `scores` 表与 `users.teacher_id`；
  旧库通过 `PRAGMA table_info` + `ALTER TABLE` 自动补列（注意先补列再建依赖新列的索引）。
- `server/security.py`：把鉴权核心（密码、JWT、白名单会话、依赖）从 `auth.py` 抽出，
  避免业务路由反向导入 `auth.py` 造成循环。
- `server/teacher.py`：教师业务路由，全部按当前登录教师做归属校验。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/teacher/gradebook` | 学生 × 作业成绩矩阵（学生页、作业页共用一次拉取） |
| GET/POST | `/teacher/assignments` | 作业列表 / 新增 |
| PUT/DELETE | `/teacher/assignments/{id}` | 修改 / 删除（级联成绩） |
| PUT | `/teacher/scores` | 按单元格批量改分；`score=null` 表示清空 |
| GET | `/techniques` | 手法列表 |
| DELETE | `/techniques/{id}` | 仅允许删除未被作业引用的手法 |

- 「标准手法」：`technique_id = NULL` 表示内置「人工批阅」；选已有手法时把名称快照进作业。
- 权限：`role` 为 `teacher`/`admin` 才能访问；学生账号 403；教师之间数据隔离。

### 11.2 客户端

- `app/student_page.py`：姓名/学号 + 动态作业列；搜索、显示全部、刷新；单元格多选、
  点列头选整列、点行号选整行；「修改成绩」批量设为同一分数（0–100），姓名/学号列不参与。
- `app/assignment_page.py`：6 列表格（题目/起始/截止/标准手法/状态/描述）、搜索、
  新增/修改/删除（删除二次确认、级联成绩）、双击行编辑、状态实时计算并着色。
- `app/technique_page.py`：列表、搜索、删除（二次确认、被引用时提示）；新增只弹
  「需要连接外部设备」的提示。
- `app/assignment_dialog.py`、`app/score_edit_dialog.py`：按实际 `.ui` 控件实现，
  按 `UI Designer Reminder.txt` 对齐了命名与列顺序；错误文案就地显示。
- `app/mainwindow.py`：把设计器的绝对定位控件重新装进布局，装配三个页面并统一加载数据；
  会话心跳与关窗登出逻辑保持不变。

### 11.3 验证

- 接口 25 项断言：成绩册结构、作业增删改、时间/手法校验、批量改分与清空、级联删除、
  学生 403、跨教师隔离，全部通过。
- GUI 44 项断言：动态列、表头、状态着色、搜索过滤、列/行选择、批量改分落库、
  对话框回填与校验、手法页，全部通过；离屏截图确认布局无重叠、表格占满页面。
- 迁移 1 项：用旧库（无 `teacher_id`）验证自动补列。

### 11.4 演示数据与未实现

- `server/seed_demo.py`：生成 5 名学生（`2023001`–`2023005`，密码 `hitsz`）、4 项作业和成绩，
  可重复执行；本次已在 `server/auth.db` 写入该演示数据（数据库已忽略，可删库重置）。
- 未实现：新增手法（依赖外部设备采集）、学生端全部功能、作业附件/题目类型等扩展字段。

---

## 12. 服务端启动入口拆分与文档同步（2026-10-17）

### 12.1 拆分

之前 `server/auth.py` 同时负责「组装 FastAPI app」和「启动 uvicorn」，带来三个问题：

- 启动参数（端口、证书、TLS）散落在路由文件末尾，改启动方式要动业务文件；
- 只想导入 app 做测试时，也会带上启动相关依赖；
- 目录职责不清晰，`auth.py` 看不出「应用」与「入口」的边界。

现在：

- **`server/auth.py`**：只组装 app（lifespan、认证端点、挂载教师路由），不再启动服务；
  直接运行它只会打印一行提示，避免旧命令静默退出。
- **`server/main.py`**：唯一启动入口，负责读取 `AUTH_PORT` / `AUTH_TLS` / `AUTH_TLS_DIR`、
  生成证书、调用 uvicorn；默认只跑 HTTPS，`AUTH_TLS=0` 才回落明文（仅调试）。
- 两种启动方式均已验证：`python server/main.py` 与 `python -m server.main`。
- 其他模块（`security.py` / `teacher.py` / `db.py` / `tls.py`）的导入方式保持不变，
  两种入口都能正确解析相对/绝对导入。

### 12.2 验证

| 检查 | 结果 |
| --- | --- |
| `python server/main.py`（默认 HTTPS 8000） | `/health` 200；`admin/hitsz` 登录、成绩册 5 学生 / 4 作业、登出正常 |
| `python -m server.main`（`AUTH_PORT=8011`） | HTTPS `/health` 200 |
| `AUTH_TLS=0`（`AUTH_PORT=8012`） | HTTP `/health` 200 |
| `python server/auth.py`（旧命令） | 打印「请使用 python server/main.py」，退出码 0 |
| 全量 `compileall` | 通过 |

### 12.3 README 同步

README 按当前进度重写：

- 新增「当前进度」表：鉴权/HTTPS、学生页、作业页、手法页已完成；主页占位、学生端未开始、采集工具未接入；
- 快速开始改为 `python server/main.py` + `python main.py`，补充演示数据命令与 `python` / `py` 的坑；
- 新增目录结构树、数据与重置、已知限制/后续、文档索引；
- 保留并整合 HTTPS、白名单会话、环境变量与接口表。

> 本节取代 §1 与 §5 中「用 `server/auth.py` 启动」的旧说法；§2.1 / §3 / §4 / §6 已就地标注历史状态。


