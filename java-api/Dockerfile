# Multi-stage build for smaller final image

# Stage 1: Build
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /build

# Copy pom.xml first for better caching
COPY pom.xml .

# Download dependencies
RUN mvn dependency:go-offline -B

# Copy source code
COPY src ./src

# Build the application
RUN mvn clean package -DskipTests

# Stage 2: Runtime
FROM eclipse-temurin:17-jre-alpine

# Install curl for healthcheck
RUN apk add --no-cache curl

WORKDIR /app

# Copy the fat JAR from builder stage
COPY --from=builder /build/target/xlsx-pivot-gateway.jar ./app.jar

# Copy static resources (if not already in JAR)
COPY --from=builder /build/src/main/resources ./resources

# Create non-root user for security
RUN addgroup -S appgroup && \
    adduser -S appuser -G appgroup && \
    chown -R appuser:appgroup /app

USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application --- include the copied resources directory on the classpath
# Use -cp and the main class so the external resources folder is visible on the classpath
ENTRYPOINT ["java", "-cp", "/app/resources:/app/app.jar", "edu.university.xlsxpivot.App"]