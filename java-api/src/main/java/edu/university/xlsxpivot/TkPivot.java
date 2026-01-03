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

/**
 * Take that handles XLSX pivot processing requests.
 * Accepts multipart form data with two XLSX files and returns a processed report.
 */
public final class TkPivot implements Take {
    
    private final PyEngineClient client;
    
    /**
     * Constructor with default Python engine URL.
     */
    public TkPivot() {
        this(new PyEngineClient("http://localhost:8000"));
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
    private Map<String, byte[]> parseMultipart(final Request req) throws Exception {
        final Map<String, byte[]> files = new HashMap<>();
        System.out.println("TkPivot.parseMultipart: entered");
        
        // Get Content-Type header to extract boundary
        String contentType = null;
        for (final String header : req.head()) {
            if (header.toLowerCase().startsWith("content-type:")) {
                contentType = header.substring(13).trim();
                break;
            }
        }
        System.out.println("TkPivot.parseMultipart: contentType header='" + contentType + "'");
        
        if (contentType == null || !contentType.contains("multipart/form-data")) {
            throw new IllegalArgumentException("Request must be multipart/form-data");
        }
        
        // Extract boundary
        final String boundaryPrefix = "boundary=";
        final int boundaryIndex = contentType.indexOf(boundaryPrefix);
        if (boundaryIndex == -1) {
            throw new IllegalArgumentException("No boundary found in Content-Type");
        }
        final String boundary = "--" + contentType.substring(boundaryIndex + boundaryPrefix.length());
        
        // Read entire body
        System.out.println("TkPivot.parseMultipart: about to read body stream");
        final byte[] body = this.readAllBytes(req.body());
        System.out.println("TkPivot.parseMultipart: finished reading body, size=" + (body == null ? 0 : body.length));
        final String bodyStr = new String(body, "UTF-8");
        
        // Split by boundary
        final String[] parts = bodyStr.split(boundary);
        
        for (final String part : parts) {
            if (part.trim().isEmpty() || part.contains("--")) {
                continue;
            }
            
            // Extract field name from Content-Disposition header
            final String namePrefix = "name=\"";
            final int nameStart = part.indexOf(namePrefix);
            if (nameStart == -1) {
                continue;
            }
            
            final int nameEnd = part.indexOf("\"", nameStart + namePrefix.length());
            final String fieldName = part.substring(nameStart + namePrefix.length(), nameEnd);
            
            // Find the start of actual file content (after double CRLF)
            final String doubleCrlf = "\r\n\r\n";
            final int contentStart = part.indexOf(doubleCrlf);
            if (contentStart == -1) {
                continue;
            }
            
            // Extract binary content
            final int binaryStart = bodyStr.indexOf(part) + contentStart + doubleCrlf.length();
            int binaryEnd = binaryStart;
            
            // Find next boundary
            for (int i = binaryStart; i < body.length; i++) {
                if (i + boundary.length() <= body.length) {
                    final String check = new String(body, i, boundary.length(), "UTF-8");
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
        }
        
        return files;
    }
    
    /**
     * Read all bytes from an input stream.
     * 
     * @param input Input stream
     * @return Byte array
     * @throws Exception If reading fails
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