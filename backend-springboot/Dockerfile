FROM maven:3.9.8-eclipse-temurin-17 AS build
WORKDIR /app
COPY backend-springboot/pom.xml ./pom.xml
RUN mvn -q -DskipTests dependency:go-offline
COPY backend-springboot/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app

# 👇 关键：换源 + 强制 IPv4（双保险）
RUN sed -i 's|http://archive.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list && \
    sed -i 's|http://security.ubuntu.com/ubuntu|https://mirrors.aliyun.com/ubuntu|g' /etc/apt/sources.list && \
    apt-get -o Acquire::ForceIPv4=true update && \
    apt-get install -y sshpass && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/target/backend-springboot-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 6200
ENTRYPOINT ["java", "-jar", "/app/app.jar"]