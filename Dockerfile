FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt pyproject.toml ./

COPY prod_assistance ./prod_assistance

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "router.main:app", "--host", "0.0.0.0", "--port", "8080"]

