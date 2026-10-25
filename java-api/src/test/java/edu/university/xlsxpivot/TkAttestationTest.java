package edu.university.xlsxpivot;

import java.io.IOException;
import java.net.ConnectException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.takes.rq.RqFake;
import org.takes.rs.RsPrint;

import static org.hamcrest.CoreMatchers.allOf;
import static org.hamcrest.CoreMatchers.containsString;
import static org.hamcrest.CoreMatchers.equalTo;
import static org.hamcrest.CoreMatchers.not;
import static org.junit.Assert.assertThat;

public final class TkAttestationTest {

    @Test
    public void cannotDropQueryString() throws Exception {
        final AtomicReference<String> target = new AtomicReference<>();
        new TkAttestation(
            (method, path, headers, body) -> {
                target.set(path);
                return TkAttestationTest.answer(200);
            }
        ).act(new RqFake("GET", "/attestation?error=wrong"));
        assertThat("Gateway lost the query string", target.get(), equalTo("/attestation?error=wrong"));
    }

    @Test
    public void cannotLoseCsrfToken() throws Exception {
        final AtomicReference<Map<String, String>> sent = new AtomicReference<>();
        new TkAttestation(
            (method, path, headers, body) -> {
                sent.set(headers);
                return TkAttestationTest.answer(202);
            }
        ).act(TkAttestationTest.post("X-CSRF-Token: token-1"));
        assertThat("Gateway dropped the CSRF token", sent.get().get("X-CSRF-Token"), equalTo("token-1"));
    }

    @Test
    public void cannotPassUnlistedRequestHeaders() throws Exception {
        final AtomicReference<Map<String, String>> sent = new AtomicReference<>();
        new TkAttestation(
            (method, path, headers, body) -> {
                sent.set(headers);
                return TkAttestationTest.answer(202);
            }
        ).act(TkAttestationTest.post("X-Internal-Admin: yes"));
        assertThat(
            "Gateway forwarded a header the service never asked for",
            sent.get().containsKey("X-Internal-Admin"),
            equalTo(false)
        );
    }

    @Test
    public void cannotLoseRequestBody() throws Exception {
        final AtomicReference<String> sent = new AtomicReference<>();
        new TkAttestation(
            (method, path, headers, body) -> {
                sent.set(new String(body, StandardCharsets.UTF_8));
                return TkAttestationTest.answer(202);
            }
        ).act(TkAttestationTest.post("Accept: application/json"));
        assertThat("Gateway lost the request body", sent.get(), equalTo("{\"attestation\":1}"));
    }

    @Test
    public void cannotFollowLoginRedirect() throws Exception {
        final Map<String, List<String>> headers = new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
        headers.put("Location", List.of("/attestation"));
        headers.put("Set-Cookie", List.of("attestation_session=abc; HttpOnly; Secure; SameSite=strict"));
        assertThat(
            "Gateway changed the login redirect or its cookie",
            new RsPrint(
                new TkAttestation(
                    (method, path, sent, body) -> new ProxiedResponse(303, headers, new byte[0])
                ).act(new RqFake("POST", "/attestation/login", "username=a"))
            ).print(),
            allOf(
                containsString("HTTP/1.1 303"),
                containsString("Location: /attestation"),
                containsString("Set-Cookie: attestation_session=abc; HttpOnly; Secure; SameSite=strict")
            )
        );
    }

    @Test
    public void cannotLeakInternalResponseHeaders() throws Exception {
        final Map<String, List<String>> headers = new TreeMap<>(String.CASE_INSENSITIVE_ORDER);
        headers.put("Server", List.of("uvicorn"));
        headers.put("Content-Type", List.of("application/json"));
        assertThat(
            "Gateway exposed the Python server header",
            new RsPrint(
                new TkAttestation(
                    (method, path, sent, body) -> new ProxiedResponse(200, headers, "{}".getBytes(StandardCharsets.UTF_8))
                ).act(new RqFake("GET", "/attestation/api/me"))
            ).print(),
            not(containsString("uvicorn"))
        );
    }

    @Test
    public void cannotHideEngineOutage() throws Exception {
        assertThat(
            "Gateway hid that the attestation service is down",
            new RsPrint(
                new TkAttestation(
                    (method, path, headers, body) -> {
                        throw new ConnectException("Connection refused");
                    }
                ).act(new RqFake("GET", "/attestation"))
            ).print(),
            allOf(containsString("HTTP/1.1 502"), containsString("недоступен"))
        );
    }

    @Test
    public void cannotAcceptHugeBody() throws Exception {
        final byte[] huge = new byte[70 * 1024];
        Arrays.fill(huge, (byte) 'a');
        assertThat(
            "Gateway forwarded an oversized request",
            new RsPrint(
                new TkAttestation(
                    (method, path, headers, body) -> TkAttestationTest.answer(200)
                ).act(
                    new RqFake(
                        Arrays.asList("POST /attestation/login HTTP/1.1", "Content-Length: " + huge.length),
                        huge
                    )
                )
            ).print(),
            containsString("HTTP/1.1 413")
        );
    }

    @Test
    public void cannotWaitForBodyOfGetRequest() throws Exception {
        final AtomicReference<Integer> length = new AtomicReference<>();
        new TkAttestation(
            (method, path, headers, body) -> {
                length.set(body.length);
                return TkAttestationTest.answer(200);
            }
        ).act(
            new RqFake(
                Arrays.asList("GET /attestation HTTP/1.1", "Host: localhost"),
                new java.io.InputStream() {
                    @Override
                    public int read() {
                        throw new IllegalStateException("Gateway read a body nobody declared");
                    }
                }
            )
        );
        assertThat("Gateway read a body that has no Content-Length", length.get(), equalTo(0));
    }

    private static RqFake post(final String header) {
        final String body = "{\"attestation\":1}";
        return new RqFake(
            Arrays.asList(
                "POST /attestation/api/jobs HTTP/1.1",
                "Content-Type: application/json",
                header,
                "Content-Length: " + body.length()
            ),
            body
        );
    }

    private static ProxiedResponse answer(final int status) throws IOException {
        return new ProxiedResponse(status, new TreeMap<>(String.CASE_INSENSITIVE_ORDER), new byte[0]);
    }
}
