FROM python:3.11-slim
WORKDIR /
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000 5432
CMD ["uvicorn","server:app","--port","8000","--host","0.0.0.0"]
