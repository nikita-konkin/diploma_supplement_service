package edu.university.xlsxpivot;

import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithStatus;
import org.takes.rs.RsWithType;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;
import java.io.IOException;
import java.io.EOFException;

/**
 * Take that handles XLSX pivot processing requests.
 * Accepts multipart form data with two XLSX files and returns a processed report.
 */
public final class TkPivot implements Take {
    
    private final PyEngineClient client;
    
    /**
     * Constructor with default Python engine URL.
     */
    // public TkPivot() {
    //     this(new PyEngineClient("http://localhost:8000"));
    // }
    
    public TkPivot() {
        this(new PyEngineClient(
            System.getenv().getOrDefault("PYTHON_ENGINE_URL", "http://python-engine:8000")
        ));
    }

    /**
     * Constructor with custom Python engine client.
     * 
     * @param client Python engine HTTP client
     */
    public TkPivot(final PyEngineClient client) {
        this.client = client;
    }
    
    @Override
    public Response act(final Request req) throws Exception {
    
        System.out.println("TkPivot: received request, starting processing");
        try {
            // Parse multipart form data manually
            final Map<String, byte[]> files = this.parseMultipart(req);
            System.out.println("TkPivot: parsed multipart, files found: " + files.keySet());
            
            // Extract files
            final byte[] scoresBytes = files.get("scores_xlsx");
            final byte[] disciplinesBytes = files.get("disciplines_xlsx");
            
            // Validate file presence
            if (scoresBytes == null || disciplinesBytes == null) {
                return new RsWithStatus(
                    new RsWithType(
                        new RsWithBody("{\"error\":\"Both scores_xlsx and disciplines_xlsx are required\"}"),
                        "application/json"
                    ),
                    400
                );
            }
            
            // Validate file sizes
            if (scoresBytes.length == 0 || disciplinesBytes.length == 0) {
                return new RsWithStatus(
                    new RsWithType(
                        new RsWithBody("{\"error\":\"Uploaded files are empty\"}"),
                        "application/json"
                    ),
                    400
                );
            }
            
            // Forward to Python engine
            System.out.println("TkPivot: forwarding to Python engine");
            final byte[] result = this.client.processPivot(scoresBytes, disciplinesBytes);
            System.out.println("TkPivot: received response from Python engine, size=" + (result == null ? 0 : result.length));
            
            // Return processed XLSX file
            return new RsWithType(
                new RsWithBody(result),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            );
            
        } catch (final IllegalArgumentException e) {
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
            return new RsWithStatus(
                new RsWithType(
                    new RsWithBody(
                        String.format("{\"error\":\"Processing failed: %s\"}", e.getMessage())
                    ),
                    "application/json"
                ),
                500
            );
        }
    }
    
    /**
     * Parse multipart form data from request.
     * Simple parser that extracts file contents by name.
     * 
     * @param req HTTP request
     * @return Map of field name to file bytes
     * @throws Exception If parsing fails
     */
private Map<String, byte[]> parseMultipart(final Request req) throws IOException  {
    final Map<String, byte[]> files = new HashMap<>();
    System.out.println("TkPivot.parseMultipart: entered");
    
    // Get boundary
    String boundary = extractBoundary(req);
    if (boundary == null) {
        throw new IllegalArgumentException("No boundary found");
    }
    
    System.out.println("TkPivot.parseMultipart: boundary='" + boundary + "'");
    byte[] boundaryBytes = boundary.getBytes("UTF-8");
    
    // Read body
    final int length = this.contentLength(req);
    System.out.println("TkPivot.parseMultipart: Content-Length=" + length);
    final byte[] body = this.readFixedBytes(req.body(), length);
    System.out.println("TkPivot.parseMultipart: Body size=" + body.length);
    
    // Save raw body for debugging
    saveDebugFile("/tmp/raw_body.bin", body);
    
    // Find first boundary
    int pos = findBytes(body, boundaryBytes, 0);
    if (pos == -1) {
        throw new IllegalArgumentException("No boundary found in body");
    }
    
    System.out.println("TkPivot.parseMultipart: First boundary at position " + pos);
    
    // Process each part
    while (true) {
        // Move to start of part (after boundary)
        pos += boundaryBytes.length;
        
        // Skip newline after boundary
        if (pos < body.length && body[pos] == '\r') pos++;
        if (pos < body.length && body[pos] == '\n') pos++;
        
        // Find end of headers (empty line)
        int headerEnd = findHeaderEnd(body, pos);
        if (headerEnd == -1) {
            break; // No more parts
        }
        
        // Parse headers to get field name
        String headers = new String(body, pos, headerEnd - pos, "UTF-8");
        String fieldName = extractFieldName(headers);
        
        if (fieldName != null) {
            // Content starts after empty line
            int contentStart = headerEnd;
            
            // Find next boundary
            int nextBoundary = findBytes(body, boundaryBytes, contentStart);
            if (nextBoundary == -1) {
                nextBoundary = body.length;
            }
            
            // Adjust for newline before boundary
            int contentEnd = nextBoundary;
            if (contentEnd > contentStart && contentEnd - 1 < body.length) {
                if (body[contentEnd - 1] == '\n') {
                    contentEnd--;
                    if (contentEnd > contentStart && body[contentEnd - 1] == '\r') {
                        contentEnd--;
                    }
                }
            }
            
            // Extract file content
            if (contentEnd > contentStart) {
                byte[] fileContent = new byte[contentEnd - contentStart];
                System.arraycopy(body, contentStart, fileContent, 0, fileContent.length);
                files.put(fieldName, fileContent);
                
                System.out.println("TkPivot.parseMultipart: Extracted " + fieldName + 
                                 " (" + fileContent.length + " bytes)");
                
                // Save for debugging
                saveDebugFile("/tmp/" + fieldName + ".xlsx", fileContent);
                
                // Check signature
                checkFileSignature(fieldName, fileContent);
            }
            
            // Move to next boundary
            pos = nextBoundary;
        } else {
            // No field name found, skip to next boundary
            int nextBoundary = findBytes(body, boundaryBytes, headerEnd);
            if (nextBoundary == -1) break;
            pos = nextBoundary;
        }
        
        // Check if this is the last boundary (ends with --)
        if (pos + 2 < body.length && body[pos + boundaryBytes.length] == '-' && 
            body[pos + boundaryBytes.length + 1] == '-') {
            break; // Last boundary
        }
    }
    
    System.out.println("TkPivot.parseMultipart: Found " + files.size() + " files");
    return files;
}


private String extractBoundary(Request req) throws IOException  {
    for (final String header : req.head()) {
        if (header.toLowerCase().startsWith("content-type:")) {
            final String ct = header.substring(13).trim();
            final int idx = ct.indexOf("boundary=");
            if (idx != -1) {
                String boundary = ct.substring(idx + 9);
                if (boundary.startsWith("\"")) {
                    boundary = boundary.substring(1, boundary.length() - 1);
                }
                return "--" + boundary;
            }
        }
    }
    return null;
}

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

private int findHeaderEnd(byte[] body, int start) {
    for (int i = start; i < body.length - 3; i++) {
        // Look for \r\n\r\n
        if (body[i] == '\r' && body[i+1] == '\n' && 
            body[i+2] == '\r' && body[i+3] == '\n') {
            return i + 4;
        }
        // Look for \n\n
        if (body[i] == '\n' && body[i+1] == '\n') {
            return i + 2;
        }
    }
    return -1;
}

private String extractFieldName(String headers) {
    int nameStart = headers.indexOf("name=\"");
    if (nameStart == -1) return null;
    
    int nameEnd = headers.indexOf("\"", nameStart + 6);
    if (nameEnd == -1) return null;
    
    return headers.substring(nameStart + 6, nameEnd);
}

private void saveDebugFile(String filename, byte[] data) {
    try {
        java.nio.file.Files.write(java.nio.file.Paths.get(filename), data);
        System.out.println("Saved debug file: " + filename);
    } catch (Exception e) {
        System.out.println("Could not save debug file: " + e.getMessage());
    }
}

private void checkFileSignature(String fieldName, byte[] data) {
    if (data.length >= 4) {
        if (data[0] == 'P' && data[1] == 'K' && data[2] == 3 && data[3] == 4) {
            System.out.println("✓ " + fieldName + ": Valid Excel signature");
        } else {
            System.out.print("✗ " + fieldName + ": Invalid signature - ");
            for (int i = 0; i < Math.min(4, data.length); i++) {
                System.out.print(String.format("%02X ", data[i] & 0xFF));
            }
            System.out.println();
        }
    }
}

    /**
     * Read all bytes from an input stream.
     * 
     * @param input Input stream
     * @return Byte array
     * @throws Exception If reading fails
     */
    private byte[] readAllBytes(final InputStream input) throws IOException  {
        final ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        final byte[] data = new byte[8192];
        int bytesRead;
        
        while ((bytesRead = input.read(data)) != -1) {
            buffer.write(data, 0, bytesRead);
        }
        
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