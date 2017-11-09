#!/bin/bash

<<EOF
Commands executed after running girder/girder docker to have mongodb available inside.

docker run --name girder_mongodb --entrypoint bash --detach -t -p 8080:8080 girder/girder
docker start girder_mongodb
docker exec -it girder_mongodb bash
EOF

(
    set -e -u
    # From: https://jira.mongodb.org/browse/SERVER-21812
    dpkg-divert --local --rename --add /etc/init.d/mongod
    ln -s /bin/true /etc/init.d/mongod
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927 && \
        echo 'deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.2 multiverse' > /etc/apt/sources.list.d/mongodb.list && \
        apt-get update && \
        apt-get install -yq mongodb-org
)
mkdir -p /data/db
mongod &
girder-server
