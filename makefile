DATE := $(shell date '+%Y-%m-%d')

docker:
	docker stop bid
	docker rm bid
	docker build -t bid-img .
	docker run -it -p 8000:8000 -p 5432:5432 --env-file .env --name bid bid-img

server:
	uvicorn server:app --reload

dev:
	docker build -t tutecktechnologies/tms-bidding:$(DATE) -t tutecktechnologies/tms-bidding:latest . --platform=linux/amd64
	docker push tutecktechnologies/tms-bidding:$(DATE)
	docker push tutecktechnologies/tms-bidding:latest

