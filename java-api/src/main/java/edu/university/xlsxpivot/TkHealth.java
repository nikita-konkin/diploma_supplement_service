package edu.university.xlsxpivot;

import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsJson;
import java.io.IOException;

import javax.json.Json;
import java.time.Instant;

/**
 * Health check endpoint for monitoring service availability.
 */
public final class TkHealth implements Take {
    
    @Override
    public Response act(final Request req) throws IOException {
        return new RsJson(
            Json.createObjectBuilder()
                .add("status", "healthy")
                .add("service", "xlsx-pivot-gateway")
                .add("timestamp", Instant.now().toString())
                .build()
        );
    }
}