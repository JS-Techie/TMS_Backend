DATE := $(shell date '+%Y-%m-%d')

docker:
	docker stop bid
	docker rm bid
	docker build -t bid-img .
	docker run -it -p 8000:8000 -p 5432:5432 --env-file .env --name bid bid-img

server:
	uvicorn server:app --reload

dev:
	docker build -t mehultuteck/tms-bidding:$(DATE) -t mehultuteck/tms-bidding:latest . --platform=linux/amd64
	docker push mehultuteck/tms-bidding:$(DATE)
	docker push mehultuteck/tms-bidding:latest