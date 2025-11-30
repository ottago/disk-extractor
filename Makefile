.PHONY: help clean veryclean build rebuild up stop down logs
.DEFAULT_GOAL := help


# Catch-all target to handle extra arguments
%:
	@:

# Fancy magic to display the comments starting with double hashes.
help:			## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build:			## Build the Docker container
	@echo "Building disk-extractor container..."
	docker-compose build

rebuild:		## Rebuild the Docker container from scratch
	@echo "Rebuilding disk-extractor container..."
	docker-compose build --no-cache

run:			## Runs the app in the forground
	docker-compose up

up:			## Start the container in the background
	@echo "Starting disk-extractor..."
	docker-compose up -d

stop:			## Stop the container
	@echo "Stopping disk-extractor..."
	docker-compose stop

down:			## Stop and remove the container
	@echo "Stopping and removing disk-extractor..."
	docker-compose down

clean: down		## Clean build artifacts and remove container
	@echo "Cleaning build artifacts..."
	docker rm -f disk-extractor 2>/dev/null || true
	docker rmi -f disk-extractor_disk-extractor 2>/dev/null || true

veryclean: clean	## Clean everything including old images and networks
	@echo "Cleaning Docker system..."
	docker system prune -f
	docker network prune -f
	docker volume prune -f

logs:			## Tail container logs
	docker-compose logs -f

