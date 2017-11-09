#!/bin/bash
set -e -u -x

cur_dir=$(cd $(dirname $0) && pwd)
cd ${cur_dir}

echo "[ Docker Setup ]"
./docker/build.sh #> /dev/null

echo "[ Server Setup (on Server) ]"
server=$(docker run --entrypoint bash --detach --rm -t -p 8080:8080 -v ${cur_dir}:/mnt external_data_server)
echo -e "server:\n${server}"
docker exec -t ${server} /mnt/setup_server.sh #> /dev/null
docker exec -t ${server} bash -c "{ mongod& } && girder-server" > /dev/null &
# https://stackoverflow.com/a/20686101/7829525
ip_addr=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${server})
# Use HTTP - https://serverfault.com/a/861580/443276
url="http://${ip_addr}:8080"
# Wait for server to initialize.
sleep 2

echo "[ Client Setup (on Client) ]"
client=$(docker run --detach --rm -t -v ${cur_dir}:/mnt external_data_client)
echo -e "client:\n${client}"

docker exec -t ${client} /mnt/setup_client.sh ${url} /mnt/build

echo "[ Run Tests (on Client) ]"
docker exec -t ${client} /mnt/test_client.sh

echo "[ Stopping (and removing) ]"
docker stop ${server} ${client}
