#!/bin/bash
set -e -u -x

rm_flags=--rm
no_stop=
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-rm)
            rm_flags=
            no_stop=1
            shift;;
        --no-stop)
            no_stop=1
            shift;;
        *)
            echo "Invalid argument: ${1}"
            exit 1;;
    esac
done

cur_dir=$(cd $(dirname $0) && pwd)
cd ${cur_dir}

echo "[ Docker Setup ]"
./docker/build.sh

echo "[ Server Setup (on Server) ]"
server=$(docker run --entrypoint bash --detach ${rm_flags} -t -p 8080:8080 -v ${cur_dir}:/mnt external_data_server)
echo -e "server:\n${server}"
docker exec -t ${server} /mnt/setup_server.sh
docker exec -t ${server} bash -c "{ mongod& } && girder-server" > /dev/null &
# https://stackoverflow.com/a/20686101/7829525
ip_addr=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${server})
# Use HTTP - https://serverfault.com/a/861580/443276
url="http://${ip_addr}:8080"
# Wait for server to initialize.
sleep 2

echo "[ Client Setup (on Client) ]"
client=$(docker run --detach ${rm_flags} -t -v ${cur_dir}:/mnt external_data_client)
echo -e "client:\n${client}"

(
    out_dir=${cur_dir}/build
    mkdir -p ${out_dir}
    # Clear out.
    rm -rf ${out_dir}/{bazel_external_data,bazel_pkg_girder_test}
    # Copy in local source directory.
    workspace_dir=../../..
    tgt_dir=${out_dir}/bazel_external_data
    mkdir -p ${tgt_dir}
    cp -r ${workspace_dir}/{WORKSPACE,BUILD.bazel,src,tools} ${tgt_dir}/
    # Copy in test respository, remove cruft
    cp -r ./bazel_pkg_girder_test ${out_dir}
    cd ${out_dir}/bazel_pkg_girder_test
    rm -rf bazel-*
    sed -i 's#path = .*,$#path = dirname(__workspace_dir__) + "/bazel_external_data",#g' WORKSPACE
)

docker exec -t ${client} /mnt/setup_client.sh ${url} /mnt/build

echo "[ Run Tests (on Client) ]"
docker exec -t ${client} /mnt/test_client.sh

if [[ -z "${no_stop}" ]]; then
    echo "[ Stopping ]"
    docker stop ${server} ${client}
else
    echo "Containers still running:"
    echo -e "  server: ${server}\n  client: ${client}"
fi
