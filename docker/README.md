# Docker 部署指南

## 快速开始

```bash
# 1. 构建并启动
docker compose up -d

# 2. 登录 (获取二维码)
docker compose exec cli xhs login

# 3. 使用 CLI
docker compose exec cli xhs search "美食"
docker compose exec cli xhs like 1
docker compose exec cli xhs publish -t "标题" -c "正文" -i /app/data/images/photo.jpg
```

## 发布图片

将图片放入 `docker/data/images/` 目录，容器内路径为 `/app/data/images/`：

```bash
# 复制图片到挂载目录
cp ~/photos/cover.jpg docker/data/images/

# 发布
docker compose exec cli xhs publish -t "美食分享" -c "好吃!" -i /app/data/images/cover.jpg
```

## 配置代理

海外用户需要代理：

```bash
# 方式 1: 环境变量
XHS_PROXY=http://host.docker.internal:7897 docker compose up -d

# 方式 2: .env 文件
echo "XHS_PROXY=http://host.docker.internal:7897" > .env
docker compose up -d
```

## 数据持久化

| 宿主机路径 | 容器路径 | 说明 |
|-----------|---------|------|
| `docker/data/cookies/` | `/app/data/cookies/` | 登录 Cookies |
| `docker/data/images/` | `/app/data/images/` | 图片/视频文件 |

## 日志

```bash
docker compose logs -f          # 实时日志
docker compose logs --tail 100  # 最后 100 行
```

## 停止

```bash
docker compose down             # 停止并移除容器
docker compose down -v          # 同时移除数据卷
```

## 注意事项

- MCP 二进制从上游 `xpzouying/xiaohongshu-mcp` Docker 镜像获取
- 首次构建需要下载 Chrome，可能需要几分钟
- 登录态保存在 `docker/data/cookies/`，重建容器不会丢失
