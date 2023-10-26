FROM python:3.8-alpine

ENV PYTHONUNBUFFERED 1
RUN apk update
RUN apk add make
RUN apk add musl-dev wget git build-base linux-headers g++ gcc libffi-dev openssl-dev cargo

#mysql client
RUN apk add --no-cache mariadb-connector-c-dev
RUN apk update && apk add mariadb-dev && pip3 install mysqlclient && apk del mariadb-dev

RUN apk add netcat-openbsd

RUN ln -s /usr/include/locale.h /usr/include/xlocale.h

RUN mkdir /app
WORKDIR /app
RUN pip3 install --upgrade pip setuptools
COPY ./requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt
RUN apk add --no-cache libstdc++
RUN apk del musl-dev wget git build-base linux-headers g++ gcc libffi-dev openssl-dev cargo
COPY . /app
EXPOSE 5000
RUN chmod +x /app/start.sh
ENTRYPOINT ["./start.sh"]