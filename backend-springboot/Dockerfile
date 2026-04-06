FROM maven:3.9.8-eclipse-temurin-17 AS build
WORKDIR /app
COPY backend-springboot/pom.xml ./pom.xml
RUN mvn -q -DskipTests dependency:go-offline
COPY backend-springboot/src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
RUN apt-get update && apt-get install -y sshpass && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/backend-springboot-0.0.1-SNAPSHOT.jar app.jar
EXPOSE 6200
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
