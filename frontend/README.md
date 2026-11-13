# frontend

## 使用步骤

1. 复制 `.env.example` 为 `.env`
2. 执行 `npm install`
3. 执行 `npm run dev`
4. 确保后端运行在 `http://localhost:8000`

## 当前功能

- 健康检查
- 案件录入并调用 `/mediate`
- 拉取 `/mock/cases`
- 查看 `/mock/mediation/{case_id}`
- 将 Mock 案例填入表单
- 展示调解结果、摘要、来源与人工复核状态
