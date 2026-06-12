package edu.university.xlsxpivot;

import java.io.IOException;
import java.io.StringReader;
import javax.json.Json;
import javax.json.JsonObject;
import javax.json.JsonReader;
import javax.json.JsonValue;

/**
 * Failure returned by one of the Python services.
 */
public final class DownstreamServiceException extends IOException {

    private static final long serialVersionUID = 1L;

    private final int status;

    public DownstreamServiceException(final int status, final String message) {
        super(message);
        this.status = status;
    }

    public int status() {
        return this.status;
    }

    public static DownstreamServiceException from(
        final int status,
        final String body,
        final String service
    ) {
        String message = "";
        if (body != null && !body.isBlank()) {
            message = DownstreamServiceException.message(body);
        }
        if (message.isBlank()) {
            message = String.format("%s returned HTTP %d", service, status);
        }
        return new DownstreamServiceException(status, message);
    }

    private static String message(final String body) {
        try (JsonReader reader = Json.createReader(new StringReader(body))) {
            final JsonObject json = reader.readObject();
            for (final String key : new String[] {"detail", "error", "message"}) {
                if (json.containsKey(key)) {
                    final JsonValue value = json.get(key);
                    if (value.getValueType() == JsonValue.ValueType.STRING) {
                        return json.getString(key);
                    }
                    return value.toString();
                }
            }
        } catch (final RuntimeException ignored) {
            // The downstream service may return plain text or an HTML proxy error.
        }
        return body.trim();
    }
}
