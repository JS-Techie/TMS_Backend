docker:
	docker stop bid
	docker rm bid
	docker build -t bid-img .
	docker run -it -p 8000:8000 -p 5432:5432 --env-file .env --name bid bid-img

server:
	uvicorn server:app --reload