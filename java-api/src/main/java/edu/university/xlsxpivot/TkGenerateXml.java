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
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import java.io.IOException;
import java.io.EOFException;


/**
 * Take that handles XML diploma generation requests.
 * Proxies requests to Python XML generation service.
 */
public final class TkGenerateXml implements Take {
    
    private static final String CRLF = "\r\n";
    
    @Override
    public Response act(final Request req) throws Exception {
        try {
            System.out.println("TkGenerateXml: received request, starting processing");
            
            // Parse multipart form data
            final Map<String, byte[]> files = new HashMap<>();
            final Map<String, String> params = new HashMap<>();
            
            this.parseMultipartRequest(req, files, params);
            
            System.out.println("TkGenerateXml: parsed multipart, files found: " + files.keySet());
            System.out.println("TkGenerateXml: params found: " + params.keySet());
            
            // Validate required files
            if (!files.containsKey("pivot_table") || !files.containsKey("student_info")) {
                System.out.println("TkGenerateXml: Missing required files");
                return new RsWithStatus(
                    new RsWithType(
                        new RsWithBody("{\"error\":\"pivot_table and student_info are required\"}"),
                        "application/json"
                    ),
                    400
                );
            }
            
            // Validate file sizes
            if (files.get("pivot_table").length == 0 || files.get("student_info").length == 0) {
                System.out.println("TkGenerateXml: Files are empty");
                return new RsWithStatus(
                    new RsWithType(
                        new RsWithBody("{\"error\":\"Uploaded files are empty\"}"),
                        "application/json"
                    ),
                    400
                );
            }
            
            // Forward to Python XML service
            System.out.println("TkGenerateXml: forwarding to XML service");
            final byte[] result = this.forwardToXmlService(files, params);
            System.out.println("TkGenerateXml: received response from XML service, size=" + result.length);
            
            // Return XML file
            return new RsWithType(
                new RsWithBody(result),
                "application/xml"
            );
            
        } catch (final IllegalArgumentException e) {
            System.out.println("TkGenerateXml: IllegalArgumentException - " + e.getMessage());
            return new RsWithStatus(
                new RsWithType(
                    new RsWithBody(
                        String.format("{\"error\":\"%s\"}", e.getMessage())
                    ),
                    "application/json"
                ),
                400
            );
        } catch (final Exception e) {
            System.out.println("TkGenerateXml: Exception - " + e.getClass().getName() + ": " + e.getMessage());
            e.printStackTrace();
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
    System.out.println("TkGenerateXml.parseMultipartRequest: entered");
    
    // Get Content-Type header
    String contentType = null;
    for (final String header : req.head()) {
        if (header.toLowerCase().startsWith("content-type:")) {
            contentType = header.substring(13).trim();
            break;
        }
    }

    System.out.println("TkGenerateXml.parseMultipartRequest: contentType header='" + contentType + "'");
    
    if (contentType == null || !contentType.contains("multipart/form-data")) {
        throw new IllegalArgumentException("Request must be multipart/form-data");
    }
    
    // Extract boundary
    final String boundaryPrefix = "boundary=";
    final int boundaryIndex = contentType.indexOf(boundaryPrefix);
    if (boundaryIndex == -1) {
        throw new IllegalArgumentException("No boundary found in Content-Type");
    }
    String boundary = contentType.substring(boundaryIndex + boundaryPrefix.length());
    
    // Remove quotes if present
    if (boundary.startsWith("\"") && boundary.endsWith("\"")) {
        boundary = boundary.substring(1, boundary.length() - 1);
    }
    
    boundary = "--" + boundary;
    System.out.println("TkGenerateXml.parseMultipartRequest: boundary='" + boundary + "'");
    
    // Read entire body
    final int length = this.contentLength(req);
    System.out.println("TkPivot.parseMultipart: Content-Length=" + length);
    System.out.println("TkGenerateXml.parseMultipartRequest: about to read body stream");
    final byte[] body = this.readFixedBytes(req.body(), length);
    System.out.println("TkGenerateXml.parseMultipartRequest: finished reading body, size=" + body.length);
    
    // Convert to string for parsing (but be careful!)
    final String bodyStr = new String(body, StandardCharsets.UTF_8);
    
    // Split by boundary
    final String[] parts = bodyStr.split(boundary);
    System.out.println("TkGenerateXml.parseMultipartRequest: Found " + parts.length + " parts");
    
    // Keep track of current position in bodyStr
    int currentPos = 0;
    
    for (int i = 0; i < parts.length; i++) {
        final String part = parts[i];
        
        // Skip empty parts or the closing boundary marker (which is just "--" or "--\r\n")
        String trimmed = part.trim();
        if (trimmed.isEmpty() || trimmed.equals("--") || trimmed.startsWith("--\r") || trimmed.startsWith("--\n")) {
            System.out.println("TkGenerateXml.parseMultipartRequest: Skipping part " + i);
            currentPos += part.length() + boundary.length();
            continue;
        }
        
        // Extract field name from Content-Disposition header
        final String namePrefix = "name=\"";
        final int nameStart = part.indexOf(namePrefix);
        if (nameStart == -1) {
            System.out.println("TkGenerateXml.parseMultipartRequest: No name found in part " + i);
            currentPos += part.length() + boundary.length();
            continue;
        }
        
        final int nameEnd = part.indexOf("\"", nameStart + namePrefix.length());
        final String fieldName = part.substring(nameStart + namePrefix.length(), nameEnd);
        System.out.println("TkGenerateXml.parseMultipartRequest: Found field: " + fieldName + " in part " + i);
        
        // Check if it's a file (has filename attribute)
        final boolean isFile = part.contains("filename=\"");
        System.out.println("TkGenerateXml.parseMultipartRequest: Is file: " + isFile);
        
        // Find the start of actual file content (after double CRLF)
        final String doubleCrlf = "\r\n\r\n";
        final int contentStartInPart = part.indexOf(doubleCrlf);
        if (contentStartInPart == -1) {
            System.out.println("TkGenerateXml.parseMultipartRequest: No content start found in part " + i);
            currentPos += part.length() + boundary.length();
            continue;
        }
        
        // **FIXED: Calculate byte positions using the original byte array directly**
        // Find the boundary in the byte array (not string)
        byte[] boundaryBytes = boundary.getBytes(StandardCharsets.UTF_8);
        
        // Find this part's content in the original byte array
        // Search for field name pattern in byte array
        byte[] fieldNamePattern = ("name=\"" + fieldName + "\"").getBytes(StandardCharsets.UTF_8);
        int fieldPos = findBytes(body, fieldNamePattern, 0);
        
        if (fieldPos == -1) {
            System.out.println("TkGenerateXml.parseMultipartRequest: Could not find field in byte array: " + fieldName);
            currentPos += part.length() + boundary.length();
            continue;
        }
        
        // Find content start (after headers) in byte array
        byte[] crlfcrlf = "\r\n\r\n".getBytes(StandardCharsets.UTF_8);
        int contentStartBytes = findBytes(body, crlfcrlf, fieldPos);
        
        if (contentStartBytes == -1) {
            // Try \n\n
            byte[] lflf = "\n\n".getBytes(StandardCharsets.UTF_8);
            contentStartBytes = findBytes(body, lflf, fieldPos);
            if (contentStartBytes != -1) {
                contentStartBytes += lflf.length;
            }
        } else {
            contentStartBytes += crlfcrlf.length;
        }
        
        if (contentStartBytes == -1) {
            System.out.println("TkGenerateXml.parseMultipartRequest: Could not find content start for: " + fieldName);
            currentPos += part.length() + boundary.length();
            continue;
        }
        
        // Find next boundary after content
        int nextBoundaryBytes = findBytes(body, boundaryBytes, contentStartBytes);
        if (nextBoundaryBytes == -1) {
            nextBoundaryBytes = body.length;
        }
        
        // Adjust for newline before boundary
        int contentEndBytes = nextBoundaryBytes;
        if (contentEndBytes > 0) {
            if (contentEndBytes - 1 < body.length && body[contentEndBytes - 1] == '\n') {
                contentEndBytes--;
                if (contentEndBytes > 0 && body[contentEndBytes - 1] == '\r') {
                    contentEndBytes--;
                }
            }
        }
        
        System.out.println("TkGenerateXml.parseMultipartRequest: Extracting " + fieldName + 
                         " from bytes " + contentStartBytes + " to " + contentEndBytes);
        
        if (contentEndBytes > contentStartBytes && contentEndBytes <= body.length) {
            final byte[] content = new byte[contentEndBytes - contentStartBytes];
            System.arraycopy(body, contentStartBytes, content, 0, content.length);
            
            if (isFile) {
                files.put(fieldName, content);
                System.out.println("TkGenerateXml.parseMultipartRequest: Extracted file '" + 
                                 fieldName + "' (" + content.length + " bytes)");
                
                // Check if it's a valid Excel file
                if (content.length >= 4) {
                    if (content[0] == 'P' && content[1] == 'K' && 
                        content[2] == 3 && content[3] == 4) {
                        System.out.println("TkGenerateXml.parseMultipartRequest: ✓ Valid Excel signature");
                    } else {
                        System.out.print("TkGenerateXml.parseMultipartRequest: ✗ Invalid signature - ");
                        for (int j = 0; j < Math.min(4, content.length); j++) {
                            System.out.print(String.format("%02X ", content[j] & 0xFF));
                        }
                        System.out.println();
                    }
                }
            } else {
                String textValue = new String(content, StandardCharsets.UTF_8).trim();
                params.put(fieldName, textValue);
                System.out.println("TkGenerateXml.parseMultipartRequest: Extracted param '" + 
                                 fieldName + "' = '" + textValue + "'");
            }
        } else {
            System.out.println("TkGenerateXml.parseMultipartRequest: Invalid byte range for " + fieldName + 
                             ": " + contentStartBytes + " to " + contentEndBytes);
        }
        
        // Move to next part (string position for loop control)
        currentPos += part.length() + boundary.length();
    }
    
    System.out.println("TkGenerateXml.parseMultipartRequest: Returning " + 
                     files.size() + " files and " + params.size() + " params");
}

// Helper method to find bytes in byte array
private int findBytes(byte[] array, byte[] target, int fromIndex) {
    if (fromIndex >= array.length || target.length == 0) {
        return -1;
    }
    
    outer:
    for (int i = fromIndex; i <= array.length - target.length; i++) {
        for (int j = 0; j < target.length; j++) {
            if (array[i + j] != target[j]) {
                continue outer;
            }
        }
        return i;
    }
    return -1;
}
    
    /**
     * Forward request to Python XML service.
     */
    private byte[] forwardToXmlService(
        final Map<String, byte[]> files,
        final Map<String, String> params
    ) throws Exception {
        System.out.println("TkGenerateXml.forwardToXmlService: Starting");
        System.out.println("TkGenerateXml.forwardToXmlService: Files to send: " + files.keySet());
        System.out.println("TkGenerateXml.forwardToXmlService: Params to send: " + params.keySet());
        
        final String boundary = "----WebKitFormBoundary" + UUID.randomUUID().toString().replace("-", "");
        final URL url = new URL(Config.xmlApiBase() + Config.xmlGeneratePath());
        System.out.println("TkGenerateXml.forwardToXmlService: URL=" + url);
        
        final HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        
        try {
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setDoInput(true);
            connection.setConnectTimeout(120000);
            connection.setReadTimeout(120000);
            connection.setRequestProperty("Content-Type", "multipart/form-data; boundary=" + boundary);
            connection.setRequestProperty("User-Agent", "Java-Diploma-Service");
            
            System.out.println("TkGenerateXml.forwardToXmlService: Connection created, setting up multipart...");
            
            // Build multipart body
            try (final java.io.OutputStream output = connection.getOutputStream()) {
                // Add files
                for (final Map.Entry<String, byte[]> entry : files.entrySet()) {
                    System.out.println("TkGenerateXml.forwardToXmlService: Adding file: " + entry.getKey() + 
                                     " (" + entry.getValue().length + " bytes)");
                    this.writeFilePart(output, boundary, entry.getKey(), 
                        entry.getKey() + ".xlsx", entry.getValue());
                }
                
                // Add parameters
                for (final Map.Entry<String, String> entry : params.entrySet()) {
                    System.out.println("TkGenerateXml.forwardToXmlService: Adding param: " + 
                                     entry.getKey() + " = " + entry.getValue());
                    this.writeTextPart(output, boundary, entry.getKey(), entry.getValue());
                }
                
                // End boundary
                final StringBuilder endBoundary = new StringBuilder();
                endBoundary.append("--").append(boundary).append("--").append(CRLF);
                output.write(endBoundary.toString().getBytes(StandardCharsets.UTF_8));
                output.flush();
            }
            
            System.out.println("TkGenerateXml.forwardToXmlService: Request sent, getting response code...");
            final int responseCode = connection.getResponseCode();
            System.out.println("TkGenerateXml.forwardToXmlService: Response code=" + responseCode);
            
            if (responseCode != 200) {
                System.out.println("TkGenerateXml.forwardToXmlService: Error response code " + responseCode);
                // Read error stream
                try (InputStream errorStream = connection.getErrorStream()) {
                    if (errorStream != null) {
                        String error = new String(readAllBytes(errorStream), StandardCharsets.UTF_8);
                        System.out.println("TkGenerateXml.forwardToXmlService: Error response: " + error);
                    }
                }
                throw new RuntimeException("Python service returned status " + responseCode);
            }
            
            System.out.println("TkGenerateXml.forwardToXmlService: Reading response...");
            try (InputStream input = connection.getInputStream()) {
                byte[] result = readAllBytes(input);
                System.out.println("TkGenerateXml.forwardToXmlService: Received " + result.length + " bytes");
                return result;
            }
            
        } catch (Exception e) {
            System.out.println("TkGenerateXml.forwardToXmlService: ERROR - " + e.getClass().getName() + ": " + e.getMessage());
            e.printStackTrace();
            throw e;
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
        int total = 0;
        
        while ((bytesRead = input.read(data)) != -1) {
            buffer.write(data, 0, bytesRead);
            total += bytesRead;
        }
        
        System.out.println("TkGenerateXml.readAllBytes: Total " + total + " bytes");
        return buffer.toByteArray();
    }

    private int contentLength(final Request req) throws IOException  {
        for (final String header : req.head()) {
            if (header.toLowerCase().startsWith("content-length:")) {
                return Integer.parseInt(header.substring(15).trim());
            }
        }
        throw new IllegalArgumentException("Content-Length header is missing");
    }

    private byte[] readFixedBytes(final InputStream input, final int length)
        throws IOException {

        final byte[] result = new byte[length];
        int offset = 0;

        while (offset < length) {
            final int read = input.read(result, offset, length - offset);
            if (read == -1) {
                throw new EOFException(
                    "Unexpected end of stream: expected " + length +
                    " bytes, got " + offset
                );
            }
            offset += read;
        }

        return result;
    }


}