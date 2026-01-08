package edu.university.xlsxpivot;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

/**
 * HTTP client for communicating with the Python XLSX processing engine.
 * Handles multipart/form-data requests and binary responses.
 */
public final class PyEngineClient {
    
    private static final int BUFFER_SIZE = 8192;
    private static final int TIMEOUT_MS = 300000; // 5 minutes
    
    private final String baseUrl;
    
    /**
     * Constructor.
     * 
     * @param baseUrl Base URL of the Python engine (e.g., "http://localhost:8000")
     */
    public PyEngineClient(final String baseUrl) {
        this.baseUrl = baseUrl;
    }
    
    /**
     * Process pivot request by sending two XLSX files to the Python engine.
     * 
     * @param scoresBytes Student scores XLSX file bytes
     * @param disciplinesBytes Disciplines list XLSX file bytes
     * @return Processed XLSX file bytes
     * @throws IOException If communication with Python engine fails
     */
    public byte[] processPivot(final byte[] scoresBytes, final byte[] disciplinesBytes) throws IOException {
        final String boundary = "----WebKitFormBoundary" + UUID.randomUUID().toString().replace("-", "");
        final URL url = new URL(this.baseUrl + "/pivot");
        final HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        
        try {
            // Configure connection
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setDoInput(true);
            connection.setConnectTimeout(TIMEOUT_MS);
            connection.setReadTimeout(TIMEOUT_MS);
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
            
            // Build multipart body
            try (final OutputStream output = connection.getOutputStream()) {
                // Add scores_xlsx file
                this.writeFilePart(output, boundary, "scores_xlsx", "scores.xlsx", scoresBytes);
                
                // Add disciplines_xlsx file
                this.writeFilePart(output, boundary, "disciplines_xlsx", "disciplines.xlsx", disciplinesBytes);
                
                // End boundary
                final StringBuilder endBoundary = new StringBuilder();
                endBoundary.append("--").append(boundary).append("--").append("\r\n");
                output.write(endBoundary.toString().getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
            
            // Check response status
            final int status = connection.getResponseCode();
            if (status != 200) {
                final byte[] errorBytes = this.readStream(connection.getErrorStream());
                final String error = new String(errorBytes, StandardCharsets.UTF_8);

                throw new IOException(
                    String.format("Python engine returned status %d: %s", status, error)
                );
}
            
            // Read response
            return this.readStream(connection.getInputStream());
            
        } finally {
            connection.disconnect();
        }
    }
    
    /**
     * Write a file part to the multipart output stream.
     * 
     * @param output Output stream
     * @param boundary Multipart boundary
     * @param fieldName Form field name
     * @param fileName File name
     * @param content File content bytes
     * @throws IOException If writing fails
     */
    private void writeFilePart(
        final OutputStream output,
        final String boundary,
        final String fieldName,
        final String fileName,
        final byte[] content
    ) throws IOException {
        final StringBuilder sb = new StringBuilder();
        sb.append("--").append(boundary).append("\r\n");
        sb.append("Content-Disposition: form-data; name=\"").append(fieldName);
        sb.append("\"; filename=\"").append(fileName).append("\"").append("\r\n");
        sb.append("Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        sb.append("\r\n").append("\r\n");
        
        output.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        output.write(content);
        output.write("\r\n".getBytes(StandardCharsets.UTF_8));
    }
    
    /**
     * Read all bytes from an input stream.
     * 
     * @param input Input stream
     * @return Byte array of stream content
     * @throws IOException If reading fails
     */
    private byte[] readStream(final InputStream input) throws IOException {
        if (input == null) {
            return new byte[0];
        }
        
        final ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        final byte[] data = new byte[BUFFER_SIZE];
        int bytesRead;
        
        while ((bytesRead = input.read(data, 0, data.length)) != -1) {
            buffer.write(data, 0, bytesRead);
        }
        
        buffer.flush();
        return buffer.toByteArray();
    }
}