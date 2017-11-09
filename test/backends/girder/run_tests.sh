#!/bin/bash
set -e -u -x

cur_dir=$(cd $(dirname $0) && pwd)
cd ${cur_dir}

echo "[ Get Basic Code ]"
out_dir=${cur_dir}/build
mkdir -p ${out_dir}

repo_name=bazel-large-files-with-girder
repo_dir=${out_dir}/${repo_name}
rm -rf ${repo_dir}
(
    cd ${out_dir}
    git clone https://github.com/EricCousineau-TRI/bazel-large-files-with-girder.git -b feature/external_data
)

# Download data files.
(
    cd ${out_dir}
    [[ -f small_dragon.obj ]] || \
        curl -L --progress-bar -o small_dragon.obj -O https://github.com/jcfr/bazel-large-files-with-girder/releases/download/test-data/small_dragon.obj
    [[ -f large_dragon.obj ]] || \
        curl -L --progress-bar -o large_dragon.obj -O https://github.com/jcfr/bazel-large-files-with-girder/releases/download/test-data/large_dragon.obj
)

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

info_file=${out_dir}/info.yaml
config_file=${repo_dir}/.external_data.yml
user_file=${out_dir}/external_data.user.yml
args="${url} ${info_file} ${config_file} ${user_file}"
docker exec -t ${client} /mnt/setup_client.py $(echo ${args} | sed "s#${cur_dir}#/mnt#g")

echo "[ Run Tests (on Client) ]"
docker exec -t ${client} /mnt/test_client.sh

echo "[ Stopping (and removing) ]"
docker stop ${server} ${client}
