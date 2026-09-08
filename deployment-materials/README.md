# 纯测试部署材料

本目录保存可公开提交的纯测试数据库和运行附件样本，所有名称、邮箱、订单号、地址和联系方式均为虚构内容。

- `database/demo.db`：SQLite 演示数据库，包含示例账号、4 条订单和 28 条发货申请。
- `runtime-attachments/TEST-BATCH-A.xlsx`、`TEST-BATCH-D.xlsx`：两份纯测试发货申请样本。
- 项目根目录的 `.env.example`：部署环境变量模板，密码和密钥均为占位值。
- `frontend/public/templates/`：订单导入与发货申请 Excel 模板。

这些文件用于开发、演示和部署结构参考，不是虚拟机历史业务数据库的备份。公开仓库不保存有效密码、签名密钥、生产环境连接信息或真实业务记录。
