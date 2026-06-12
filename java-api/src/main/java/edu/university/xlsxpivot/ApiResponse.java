package edu.university.xlsxpivot;

import javax.json.Json;
import org.takes.Response;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithStatus;
import org.takes.rs.RsWithType;

/**
 * JSON responses shared by gateway endpoints.
 */
public final class ApiResponse {

    private ApiResponse() {
    }

    public static Response error(final int status, final String message) {
        final String body = Json.createObjectBuilder()
            .add("error", message == null ? "Unexpected server error" : message)
            .add("status", status)
            .build()
            .toString();
        return new RsWithStatus(
            new RsWithType(new RsWithBody(body), "application/json; charset=UTF-8"),
            status
        );
    }
}
