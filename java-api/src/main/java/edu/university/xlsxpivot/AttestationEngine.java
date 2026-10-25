package edu.university.xlsxpivot;

import java.io.IOException;
import java.util.Map;

/**
 * Attestation report service behind the gateway: one HTTP exchange, passed on as is.
 */
@FunctionalInterface
public interface AttestationEngine {

    /**
     * Send one request to the service.
     *
     * @param method HTTP method
     * @param target Path with query string, e.g. "/attestation/api/me"
     * @param headers Request headers allowed through the gateway
     * @param body Request body, empty for GET
     * @return The service's answer, including error statuses and redirects
     * @throws IOException If the service cannot be reached
     */
    ProxiedResponse forward(String method, String target, Map<String, String> headers, byte[] body)
        throws IOException;
}
