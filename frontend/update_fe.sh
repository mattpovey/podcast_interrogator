#!/bin/bash
DOCKER_PREFIX=${DOCKER_PREFIX:-podcast-search}

docker build -t ${DOCKER_PREFIX}-frontend .
docker volume rm ${DOCKER_PREFIX}_app_data
docker volume rm ${DOCKER_PREFIX}_app_logs
