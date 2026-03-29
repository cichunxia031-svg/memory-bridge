FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

# 数据库存在持久化卷里
ENV DB_DIR=/data
ENV PORT=8765

EXPOSE 8765

CMD ["python", "server.py"]
