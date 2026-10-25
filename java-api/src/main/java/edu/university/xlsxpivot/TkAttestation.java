package edu.university.xlsxpivot;

import java.io.IOException;
import java.net.URI;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rq.RqHeaders;
import org.takes.rq.RqHref;
import org.takes.rq.RqLengthAware;
import org.takes.rq.RqMethod;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithHeaders;
import org.takes.rs.RsWithStatus;

/**
 * Reverse proxy for the attestation report service, a standalone component at /attestation.
 *
 * <p>The service does its own login, sessions and CSRF checks; the gateway passes through
 * only the headers those need, so nothing else from the browser reaches the service and
 * nothing internal reaches the browser. Request bodies are never logged: they carry passwords.
 */
public final class TkAttestation implements Take {

    private static final Logger LOG = LoggerFactory.getLogger(TkAttestation.class);

    private static final int TIMEOUT_MS = 60000;

    /**
     * Login form and job settings are tiny; anything bigger is not ours.
     */
    private static final int MAX_BODY_BYTES = 64 * 1024;

    private static final String[] REQUEST_HEADERS = {
        "Accept", "Content-Type", "Cookie", "X-CSRF-Token",
    };

    private static final String[] RESPONSE_HEADERS = {
        "Content-Type", "Content-Disposition", "Location", "Set-Cookie", "Cache-Control",
        "Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options",
        "Referrer-Policy", "X-Robots-Tag", "Permissions-Policy",
    };

    private final AttestationEngine engine;

    public TkAttestation() {
        this(new HttpForward(Config.attestationBase(), TIMEOUT_MS));
    }

    TkAttestation(final AttestationEngine engine) {
        this.engine = engine;
    }

    @Override
    public Response act(final Request req) throws IOException {
        final String method = new RqMethod.Base(req).method();
        final URI href = URI.create(new RqHref.Base(req).href().toString());
        final String target = href.getRawQuery() == null
            ? href.getRawPath()
            : href.getRawPath() + "?" + href.getRawQuery();
        try {
            final byte[] body = TkAttestation.body(req);
            final ProxiedResponse answer = this.engine.forward(
                method, target, TkAttestation.headers(req), body
            );
            LOG.info("Attestation {} {} -> {}", method, href.getRawPath(), answer.status());
            return TkAttestation.response(answer);
        } catch (final RejectedRequest err) {
            LOG.warn("Rejected attestation request: {}", err.getMessage());
            return ApiResponse.error(err.status(), err.getMessage());
        } catch (final IOException err) {
            LOG.error("Attestation service unreachable for {} {}: {}", method, href.getRawPath(), err.toString());
            return ApiResponse.error(502, "Сервис отчётов по аттестации недоступен. Попробуйте позже.");
        }
    }

    private static Map<String, String> headers(final Request req) throws IOException {
        final RqHeaders.Base all = new RqHeaders.Base(req);
        final Map<String, String> headers = new LinkedHashMap<>();
        for (final String name : REQUEST_HEADERS) {
            final List<String> values = all.header(name);
            if (!values.isEmpty()) {
                headers.put(name, String.join("Cookie".equals(name) ? "; " : ", ", values));
            }
        }
        // A proxy in front of us already names the client; otherwise it is our peer
        final List<String> forwarded = all.header("X-Forwarded-For");
        final List<String> remote = all.header("X-Takes-RemoteAddress");
        if (!forwarded.isEmpty()) {
            headers.put("X-Forwarded-For", String.join(", ", forwarded));
        } else if (!remote.isEmpty()) {
            headers.put("X-Forwarded-For", remote.get(0));
        }
        return headers;
    }

    /**
     * Request body, bounded by Content-Length: the raw stream of a kept-alive
     * connection never ends, so reading a GET "to the end" would hang the gateway.
     */
    private static byte[] body(final Request req) throws IOException {
        final String header = new RqHeaders.Smart(req).single("Content-Length", "");
        if (header.isEmpty()) {
            return new byte[0];
        }
        final long length;
        try {
            length = Long.parseLong(header.trim());
        } catch (final NumberFormatException err) {
            throw new RejectedRequest(400, "Неверный заголовок Content-Length");
        }
        if (length > MAX_BODY_BYTES) {
            throw new RejectedRequest(413, "Слишком большой запрос.");
        }
        return new RqLengthAware(req).body().readAllBytes();
    }

    private static Response response(final ProxiedResponse answer) {
        final List<String> headers = new ArrayList<>();
        for (final String name : RESPONSE_HEADERS) {
            for (final String value : answer.headers().getOrDefault(name, List.of())) {
                headers.add(name + ": " + value);
            }
        }
        return new RsWithStatus(
            new RsWithHeaders(new RsWithBody(answer.body()), headers),
            answer.status()
        );
    }
}
