FROM girder-dev

EXPOSE 8080

RUN mkdir -p /data/db

# From: https://jira.mongodb.org/browse/SERVER-21812
RUN \
    set -e -u && \
    dpkg-divert --local --rename --add /etc/init.d/mongod && \
    ln -s /bin/true /etc/init.d/mongod && \
    apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv EA312927 && \
        echo 'deb http://repo.mongodb.org/apt/ubuntu trusty/mongodb-org/3.2 multiverse' > /etc/apt/sources.list.d/mongodb.list && \
        apt-get update && \
        apt-get install -yq mongodb-org && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["bash", "-c", "{ mongod &   girder-server; }"]
