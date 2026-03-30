FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 数据库存在持久化卷里
ENV DB_DIR=/data
ENV PORT=8080

EXPOSE 8080

CMD ["python", "server.py"]
