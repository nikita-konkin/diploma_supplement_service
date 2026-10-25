package edu.university.xlsxpivot;

import java.util.List;
import java.util.Map;

/**
 * Status, headers and body of a downstream answer.
 */
public final class ProxiedResponse {

    private final int status;

    private final Map<String, List<String>> headers;

    private final byte[] body;

    public ProxiedResponse(final int status, final Map<String, List<String>> headers, final byte[] body) {
        this.status = status;
        this.headers = headers;
        this.body = body.clone();
    }

    public int status() {
        return this.status;
    }

    public Map<String, List<String>> headers() {
        return this.headers;
    }

    public byte[] body() {
        return this.body.clone();
    }
}
