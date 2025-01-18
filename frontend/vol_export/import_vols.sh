#!/bin/bash
DOCKER_PREFIX=${DOCKER_PREFIX:-podcast-search}

sudo docker run --rm -v ${DOCKER_PREFIX}_esdata:/usr/share/elasticsearch/data -v $(pwd):/backup busybox tar xzvf /backup/esdata.tar.gz -C /usr/share/elasticsearch/data

sudo docker run --rm -v ${DOCKER_PREFIX}_pgdata:/data -v $(pwd):/backup busybox tar xzvf /backup/pgdata.tar.gz -C /data

sudo docker run --rm -v ${DOCKER_PREFIX}_chroma-data:/chroma -v $(pwd):/backup busybox tar xzvf /backup/chroma-data.tar.gz -C /chroma

sudo docker run --rm -v ${DOCKER_PREFIX}_app_data:/app -v $(pwd):/backup busybox tar xzvf /backup/app-data.tar.gz -C /app

sudo docker container restart ${DOCKER_PREFIX}_frontend_1