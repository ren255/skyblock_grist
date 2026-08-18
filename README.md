# Quickstart

Docker と Docker Compose が必要です。

```sh
cp .env.example .env
docker compose up --build
```

- アプリ: http://localhost:8000/health
- Grist: http://localhost:3000

停止する場合:

```sh
docker compose down
```
