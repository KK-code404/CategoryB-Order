# 油品发货核销平台

<!-- CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供旧电脑虚拟机部署、开发运行和业务操作的统一入口。 -->

面向 B 类机油/添加剂整单备货、分批发货业务的核销平台。系统从专用 IMAP 邮箱读取标准 Excel 发货申请，完成订单/物料匹配、销售逐行确认、供应商邮件发送、冲销和审计追踪。

## 功能入口

- **工作台**：查看待处理、匹配异常、今日核销和剩余库存，按状态、客户、日期或关键字筛选并逐行处理。
- **订单台账**：查询订单数量、累计核销量和实时剩余未发数量。
- **发货申请**：查看申请详情，修改待处理数据，完成核销或对已核销明细执行带原因冲销。
- **邮件收件箱**：核对原始收件与 Excel 解析状态；销售和管理员可查看供应商发件并重试失败邮件。
- **操作日志**：按操作类型、日期和关键字追踪关键业务动作。
- **后台配置**：导入订单，新增或编辑代理商、供应商、物料映射与用户，支持账号启停和密码重置。

管理员可维护全部配置并处理业务；销售可核销、冲销和重试邮件；代理商账号只能查看和修正自身待处理申请。

## 前端技术栈

前端已统一为 **Vue 3 + TypeScript + Vite + Ant Design Vue**。所有页面及公共界面组件使用 `.vue` 单文件组件和 `<script setup lang="ts">`，不再依赖 React、React DOM 或 React 版 Ant Design。

- `frontend/src/App.vue`：会话恢复、登录和会话失效处理。
- `frontend/src/components/`：管理导航、申请详情、申请编辑和状态标签。
- `frontend/src/pages/`：登录、工作台、订单/发货/邮件/审计列表与后台配置。
- `frontend/src/api/client.ts`：保留原有 `/api` 接口与 HttpOnly Cookie 认证契约。
- `frontend/src/theme.ts`、`styles.css`：集中维护主题与布局，保留汽车插画和毛玻璃登录样式。

管理页面按需加载；配置表单、文件导入、角色权限和核销/冲销流程保持现有业务规则。此次前端迁移不需要修改数据库结构。

## 本地启动

1. 复制 `.env.example` 为 `.env` 并修改密码、域名、邮箱等配置。
2. 安装后端依赖并运行：

   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   $env:SEED_DEMO_DATA="true"
   $env:DATABASE_URL="sqlite:///./categoryb.db"
   .\.venv\Scripts\uvicorn app.main:app --reload --port 8000
   ```

3. 安装并运行前端：

   使用 Node.js 22.12+（Docker 构建使用 Node 22），首次安装按锁文件恢复依赖：

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

4. 打开 `http://localhost:5173`。演示数据开启时可使用 `sales@example.com / Demo123!`。

前端验证命令（在 `frontend` 目录执行）：

```bash
npm run lint
npm test
npm run build
```

测试使用 Vue Test Utils、Vitest 和 jsdom，覆盖登录/会话、导航权限、工作台、业务列表、申请修改/核销/冲销、邮件重试、主数据维护及订单导入。测试接口均使用隔离的模拟数据，不操作生产业务。jsdom 测试不替代真实浏览器的视觉验收。

## 虚拟机部署

虚拟机建议使用 Ubuntu Server 22.04+、4 核 CPU、8 GB 内存、100 GB 可用磁盘，并安装 Docker Engine 与 Compose 插件。

```bash
cp .env.example .env
# 编辑 .env：至少设置 DOMAIN、POSTGRES_PASSWORD、SECRET_KEY、INITIAL_ADMIN_PASSWORD、IMAP/SMTP 参数
docker compose up -d --build
docker compose ps
```

部署完成后可先通过 `http://虚拟机地址:5175` 在局域网内直连验证；域名入口为 `https://oilorder.kkhub.com.cn`，继续使用标准 HTTPS 端口 443。

若虚拟机已经通过 Cloudflare Tunnel 将域名转发到 `http://localhost:5175`，只启动业务容器即可，Caddy 服务无需启动：

```bash
docker compose up -d --build db redis api worker beat frontend
```

Caddy 会根据 `DOMAIN` 自动申请和续期 HTTPS 证书。请确保：

- 域名 A/AAAA 记录指向旧电脑所在网络的公网地址；
- 路由器将 TCP 80、443 转发到虚拟机；
- 虚拟机使用固定局域网地址，防火墙仅开放 22（建议限源）、80、443；
- 运营商允许入站端口并且不是无法映射的 CGNAT；
- 数据目录 `postgres_data`、`app_storage`、`caddy_data` 纳入磁盘备份。

## 业务模板

- 发货邮件主题：`[发货申请] 代理商编码 批次号`
- 附件：无宏 `.xlsx`，工作表名 `发货申请`
- 发货列：订单号、物料号、品名、数量、收货人、联系电话、收货地址、要求发货日期、备注
- 订单导入列：代理商编码、订单号、零件号、物料号、品名、订单数量、单位、品牌/供应商编码

## 常用运维

```bash
docker compose logs -f api worker beat caddy
docker compose restart
./deploy/backup.sh
```

建议通过 `crontab -e` 配置每天凌晨执行 `cd /平台目录 && ./deploy/backup.sh`，并把 `backups/` 同步到另一块磁盘。恢复前先停止业务操作，再执行：

```bash
RESTORE_CONFIRM=YES ./deploy/restore.sh backups/YYYYMMDD-HHMMSS
```

数据库迁移：`docker compose exec api alembic upgrade head`。健康检查：`https://你的域名/api/health`。平台内可从“后台配置”下载订单导入模板和代理商发货申请模板。
