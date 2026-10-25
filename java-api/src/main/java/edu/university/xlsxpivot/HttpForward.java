package edu.university.xlsxpivot;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Plain HTTP forwarding to a Python service; redirects go back to the browser, not followed.
 */
public final class HttpForward implements AttestationEngine {

    private final String base;

    private final int timeout;

    /**
     * Ctor.
     *
     * @param base Service root, e.g. "http://python-attestation-engine:8002"
     * @param timeout Connect and read timeout, milliseconds
     */
    public HttpForward(final String base, final int timeout) {
        this.base = base;
        this.timeout = timeout;
    }

    @Override
    public ProxiedResponse forward(
        final String method,
        final String target,
        final Map<String, String> headers,
        final byte[] body
    ) throws IOException {
        final HttpURLConnection connection = (HttpURLConnection) new URL(this.base + target).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setInstanceFollowRedirects(false);
            connection.setUseCaches(false);
            connection.setConnectTimeout(this.timeout);
            connection.setReadTimeout(this.timeout);
            for (final Map.Entry<String, String> header : headers.entrySet()) {
                connection.setRequestProperty(header.getKey(), header.getValue());
            }
            if (body.length > 0) {
                connection.setDoOutput(true);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(body);
                }
            }
            final int status = connection.getResponseCode();
            final Map<String, List<String>> received = new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
            for (final Map.Entry<String, List<String>> header : connection.getHeaderFields().entrySet()) {
                // the null key holds the status line
                if (header.getKey() != null) {
                    received.put(header.getKey(), header.getValue());
                }
            }
            final InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            return new ProxiedResponse(status, received, HttpForward.read(stream));
        } finally {
            connection.disconnect();
        }
    }

    private static byte[] read(final InputStream input) throws IOException {
        if (input == null) {
            return new byte[0];
        }
        try (InputStream stream = input; ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            stream.transferTo(buffer);
            return buffer.toByteArray();
        }
    }
}
