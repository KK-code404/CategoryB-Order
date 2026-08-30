# 油品发货核销平台

<!-- CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供旧电脑虚拟机部署、开发运行和业务操作的统一入口。 -->

面向 B 类机油/添加剂整单备货、分批发货业务的核销平台。系统从专用 IMAP 邮箱读取标准 Excel 发货申请，完成订单/物料匹配、销售逐行确认、供应商邮件发送、冲销和审计追踪。

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

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. 打开 `http://localhost:5173`。演示数据开启时可使用 `sales@example.com / Demo123!`。

## 虚拟机部署

虚拟机建议使用 Ubuntu Server 22.04+、4 核 CPU、8 GB 内存、100 GB 可用磁盘，并安装 Docker Engine 与 Compose 插件。

```bash
cp .env.example .env
# 编辑 .env：至少设置 DOMAIN、POSTGRES_PASSWORD、SECRET_KEY、INITIAL_ADMIN_PASSWORD、IMAP/SMTP 参数
docker compose up -d --build
docker compose ps
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
