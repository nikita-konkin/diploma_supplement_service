package edu.university.xlsxpivot;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.UUID;

/**
 * Multipart POST from the gateway to one of the Python services.
 */
public final class FormPost {

    private static final String CRLF = "\r\n";

    private final String url;

    private final String service;

    private final int timeout;

    /**
     * Ctor.
     *
     * @param url Full endpoint URL
     * @param service Service name for error messages
     * @param timeout Connect and read timeout, milliseconds
     */
    public FormPost(final String url, final String service, final int timeout) {
        this.url = url;
        this.service = service;
        this.timeout = timeout;
    }

    /**
     * Send files and text fields, return the response body.
     *
     * @throws DownstreamServiceException If the service answers with an error
     */
    public byte[] send(final Map<String, Upload> files, final Map<String, String> params)
        throws IOException {
        final String boundary = "----DiplomaGateway" + UUID.randomUUID().toString().replace("-", "");
        final HttpURLConnection connection = (HttpURLConnection) new URL(this.url).openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(this.timeout);
            connection.setReadTimeout(this.timeout);
            connection.setRequestProperty(
                "Content-Type", "multipart/form-data; boundary=" + boundary
            );
            try (OutputStream output = connection.getOutputStream()) {
                for (final Map.Entry<String, Upload> file : files.entrySet()) {
                    FormPost.write(
                        output,
                        "--" + boundary + CRLF
                            + "Content-Disposition: form-data; name=\"" + file.getKey()
                            + "\"; filename=\"" + file.getKey() + file.getValue().extension()
                            + "\"" + CRLF
                            + "Content-Type: application/octet-stream" + CRLF + CRLF
                    );
                    output.write(file.getValue().content());
                    FormPost.write(output, CRLF);
                }
                for (final Map.Entry<String, String> param : params.entrySet()) {
                    FormPost.write(
                        output,
                        "--" + boundary + CRLF
                            + "Content-Disposition: form-data; name=\"" + param.getKey()
                            + "\"" + CRLF + CRLF
                            + param.getValue() + CRLF
                    );
                }
                FormPost.write(output, "--" + boundary + "--" + CRLF);
            }
            final int status = connection.getResponseCode();
            if (status < 200 || status >= 300) {
                throw DownstreamServiceException.from(
                    status,
                    new String(FormPost.read(connection.getErrorStream()), StandardCharsets.UTF_8),
                    this.service
                );
            }
            return FormPost.read(connection.getInputStream());
        } finally {
            connection.disconnect();
        }
    }

    private static void write(final OutputStream output, final String text) throws IOException {
        output.write(text.getBytes(StandardCharsets.UTF_8));
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
