package edu.university.xlsxpivot;

import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithStatus;
import org.takes.rs.RsWithType;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Take that handles XML diploma generation requests.
 * Proxies requests to Python XML generation service.
 */
public final class TkGenerateXml implements Take {
    
    private static final String PYTHON_XML_URL = "http://localhost:8001";
    private static final String CRLF = "\r\n";
    
    @Override
    public Response act(final Request req) throws Exception {
        try {
            // Parse multipart form data
            final Map<String, byte[]> files = new HashMap<>();
            final Map<String, String> params = new HashMap<>();
            
            this.parseMultipartRequest(req, files, params);
            
            // Validate required files
            if (!files.containsKey("pivot_table") || !files.containsKey("student_info")) {
                return new RsWithStatus(
                    new RsWithType(
                        new RsWithBody("{\"error\":\"pivot_table and student_info are required\"}"),
                        "application/json"
                    ),
                    400
                );
            }
            
            // Forward to Python XML service
            final byte[] result = this.forwardToXmlService(files, params);
            
            // Return XML file
            return new RsWithType(
                new RsWithBody(result),
                "application/xml"
            );
            
        } catch (final Exception e) {
            return new RsWithStatus(
                new RsWithType(
                    new RsWithBody(
                        String.format("{\"error\":\"XML generation failed: %s\"}", e.getMessage())
                    ),
                    "application/json"
                ),
                500
            );
        }
    }
    
    /**
     * Parse multipart form data from request.
     */
    private void parseMultipartRequest(
        final Request req,
        final Map<String, byte[]> files,
        final Map<String, String> params
    ) throws Exception {
        // Get Content-Type header
        String contentType = null;
        for (final String header : req.head()) {
            if (header.toLowerCase().startsWith("content-type:")) {
                contentType = header.substring(13).trim();
                break;
            }
        }
        
        if (contentType == null || !contentType.contains("multipart/form-data")) {
            throw new IllegalArgumentException("Request must be multipart/form-data");
        }
        
        // Extract boundary
        final String boundaryPrefix = "boundary=";
        final int boundaryIndex = contentType.indexOf(boundaryPrefix);
        if (boundaryIndex == -1) {
            throw new IllegalArgumentException("No boundary found");
        }
        final String boundary = "--" + contentType.substring(boundaryIndex + boundaryPrefix.length());
        
        // Read body
        final byte[] body = this.readAllBytes(req.body());
        final String bodyStr = new String(body, StandardCharsets.UTF_8);
        
        // Parse parts
        final String[] parts = bodyStr.split(boundary);
        for (final String part : parts) {
            if (part.trim().isEmpty() || part.contains("--")) {
                continue;
            }
            
            // Extract field name
            final String namePrefix = "name=\"";
            final int nameStart = part.indexOf(namePrefix);
            if (nameStart == -1) continue;
            
            final int nameEnd = part.indexOf("\"", nameStart + namePrefix.length());
            final String fieldName = part.substring(nameStart + namePrefix.length(), nameEnd);
            
            // Check if it's a file
            final boolean isFile = part.contains("filename=\"");
            
            if (isFile) {
                // Extract file content
                final String doubleCrlf = "\r\n\r\n";
                final int contentStart = part.indexOf(doubleCrlf);
                if (contentStart == -1) continue;
                
                final int binaryStart = bodyStr.indexOf(part) + contentStart + doubleCrlf.length();
                int binaryEnd = binaryStart;
                
                for (int i = binaryStart; i < body.length; i++) {
                    if (i + boundary.length() <= body.length) {
                        final String check = new String(body, i, Math.min(boundary.length(), body.length - i), StandardCharsets.UTF_8);
                        if (check.startsWith("\r\n--") || check.startsWith("\n--")) {
                            binaryEnd = i;
                            break;
                        }
                    }
                }
                
                if (binaryEnd > binaryStart) {
                    final byte[] fileContent = new byte[binaryEnd - binaryStart];
                    System.arraycopy(body, binaryStart, fileContent, 0, fileContent.length);
                    files.put(fieldName, fileContent);
                }
            } else {
                // Extract text parameter
                final String doubleCrlf = "\r\n\r\n";
                final int contentStart = part.indexOf(doubleCrlf);
                if (contentStart != -1) {
                    final String value = part.substring(contentStart + doubleCrlf.length()).trim();
                    params.put(fieldName, value);
                }
            }
        }
    }
    
    /**
     * Forward request to Python XML service.
     */
    private byte[] forwardToXmlService(
        final Map<String, byte[]> files,
        final Map<String, String> params
    ) throws Exception {
        final String boundary = "----WebKitFormBoundary" + UUID.randomUUID().toString().replace("-", "");
        final URL url = new URL(PYTHON_XML_URL + "/generate-xml");
        final HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        
        try {
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setDoInput(true);
            connection.setConnectTimeout(120000);
            connection.setReadTimeout(120000);
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
            
            // Build multipart body
            try (final java.io.OutputStream output = connection.getOutputStream()) {
                // Add files
                for (final Map.Entry<String, byte[]> entry : files.entrySet()) {
                    this.writeFilePart(output, boundary, entry.getKey(), 
                        entry.getKey() + ".xlsx", entry.getValue());
                }
                
                // Add parameters
                for (final Map.Entry<String, String> entry : params.entrySet()) {
                    this.writeTextPart(output, boundary, entry.getKey(), entry.getValue());
                }
                
                // End boundary
                final StringBuilder endBoundary = new StringBuilder();
                endBoundary.append("--").append(boundary).append("--").append(CRLF);
                output.write(endBoundary.toString().getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
            
            // Check response
            final int status = connection.getResponseCode();
            if (status != 200) {
                throw new RuntimeException("Python service returned status " + status);
            }
            
            // Read response
            return this.readAllBytes(connection.getInputStream());
            
        } finally {
            connection.disconnect();
        }
    }
    
    /**
     * Write file part to multipart output.
     */
    private void writeFilePart(
        final java.io.OutputStream output,
        final String boundary,
        final String fieldName,
        final String fileName,
        final byte[] content
    ) throws Exception {
        final StringBuilder sb = new StringBuilder();
        sb.append("--").append(boundary).append(CRLF);
        sb.append("Content-Disposition: form-data; name=\"").append(fieldName);
        sb.append("\"; filename=\"").append(fileName).append("\"").append(CRLF);
        sb.append("Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        sb.append(CRLF).append(CRLF);
        
        output.write(sb.toString().getBytes(StandardCharsets.UTF_8));
        output.write(content);
        output.write(CRLF.getBytes(StandardCharsets.UTF_8));
    }
    
    /**
     * Write text parameter to multipart output.
     */
    private void writeTextPart(
        final java.io.OutputStream output,
        final String boundary,
        final String fieldName,
        final String value
    ) throws Exception {
        final StringBuilder sb = new StringBuilder();
        sb.append("--").append(boundary).append(CRLF);
        sb.append("Content-Disposition: form-data; name=\"").append(fieldName).append("\"");
        sb.append(CRLF).append(CRLF);
        sb.append(value).append(CRLF);
        
        output.write(sb.toString().getBytes(StandardCharsets.UTF_8));
    }
    
    /**
     * Read all bytes from input stream.
     */
    private byte[] readAllBytes(final InputStream input) throws Exception {
        final ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        final byte[] data = new byte[8192];
        int bytesRead;
        
        while ((bytesRead = input.read(data)) != -1) {
            buffer.write(data, 0, bytesRead);
        }
        
        return buffer.toByteArray();
    }
}