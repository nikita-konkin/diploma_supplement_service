package edu.university.xlsxpivot;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.takes.Request;
import org.takes.rq.RqHeaders;
import org.takes.rq.RqLengthAware;

/**
 * Multipart form of an upload request: files and text fields.
 *
 * <p>The size is checked against Content-Length before the body is read,
 * so an oversized request cannot exhaust the gateway memory. Part headers
 * are read as UTF-8: browsers send Cyrillic file names unencoded, which
 * the multipart reader of Takes rejects.
 */
public final class UploadForm {

    private static final Pattern BOUNDARY =
        Pattern.compile("boundary=(?:\"([^\"]+)\"|([^;\\s]+))", Pattern.CASE_INSENSITIVE);

    private static final Pattern NAME =
        Pattern.compile("(?:^|;)\\s*name=\"([^\"]*)\"", Pattern.CASE_INSENSITIVE);

    private static final Pattern FILENAME =
        Pattern.compile(";\\s*filename=\"([^\"]*)\"", Pattern.CASE_INSENSITIVE);

    private final Map<String, Upload> files = new HashMap<>();

    private final Map<String, String> params = new HashMap<>();

    public UploadForm(final Request req, final long limit) throws IOException {
        final RqHeaders.Smart headers = new RqHeaders.Smart(req);
        final long length = UploadForm.length(headers);
        if (length > limit) {
            throw new RejectedRequest(
                413,
                String.format(
                    "Файлы слишком большие: %.1f МБ, допустимо не больше %d МБ",
                    length / 1048576.0,
                    limit / 1048576
                )
            );
        }
        final Matcher boundary = UploadForm.BOUNDARY.matcher(headers.single("Content-Type", ""));
        if (!boundary.find()) {
            throw new RejectedRequest(
                400,
                "Запрос не содержит формы с файлами (multipart/form-data)"
            );
        }
        // Not closed on purpose: the body stream of Takes is the socket input,
        // closing it drops the connection before the response is written.
        final byte[] body = new RqLengthAware(req).body().readAllBytes();
        this.parse(
            body,
            ("--" + (boundary.group(1) == null ? boundary.group(2) : boundary.group(1)))
                .getBytes(StandardCharsets.US_ASCII)
        );
    }

    /**
     * Required non-empty file.
     *
     * @param name Form field name
     * @param title What the file is, in the words of the page
     */
    public Upload file(final String name, final String title) {
        final Upload upload = this.files.get(name);
        if (upload == null) {
            throw new RejectedRequest(400, "Не выбран файл: " + title);
        }
        if (upload.content().length == 0) {
            throw new RejectedRequest(
                400,
                String.format("Файл «%s» пустой (%s)", upload.name(), title)
            );
        }
        return upload;
    }

    public Map<String, String> params() {
        return Collections.unmodifiableMap(this.params);
    }

    /**
     * Split the body into parts. A part ends at CRLF followed by the
     * delimiter, so delimiter-like bytes inside a file do not cut it.
     */
    private void parse(final byte[] body, final byte[] delimiter) {
        int pos = UploadForm.find(body, delimiter, 0);
        while (pos >= 0) {
            pos += delimiter.length;
            if (pos + 1 < body.length && body[pos] == '-' && body[pos + 1] == '-') {
                return;
            }
            pos = UploadForm.skipLineBreak(body, pos);
            final int blank = UploadForm.find(body, "\r\n\r\n".getBytes(StandardCharsets.US_ASCII), pos);
            if (blank < 0) {
                throw new RejectedRequest(400, "Форма с файлами передана не полностью");
            }
            final String head = new String(body, pos, blank - pos, StandardCharsets.UTF_8);
            final int start = blank + 4;
            final byte[] closing = new byte[delimiter.length + 2];
            closing[0] = '\r';
            closing[1] = '\n';
            System.arraycopy(delimiter, 0, closing, 2, delimiter.length);
            final int end = UploadForm.find(body, closing, start);
            if (end < 0) {
                throw new RejectedRequest(400, "Форма с файлами передана не полностью");
            }
            this.add(head, Arrays.copyOfRange(body, start, end));
            pos = end + 2;
        }
        throw new RejectedRequest(400, "В форме нет ни одного поля");
    }

    private void add(final String head, final byte[] content) {
        final Matcher name = UploadForm.NAME.matcher(UploadForm.disposition(head));
        if (!name.find()) {
            return;
        }
        final Matcher file = UploadForm.FILENAME.matcher(UploadForm.disposition(head));
        if (file.find()) {
            this.files.putIfAbsent(name.group(1), new Upload(file.group(1), content));
        } else {
            this.params.putIfAbsent(
                name.group(1),
                new String(content, StandardCharsets.UTF_8).trim()
            );
        }
    }

    private static String disposition(final String head) {
        for (final String line : head.split("\r\n")) {
            final int colon = line.indexOf(':');
            if (colon > 0 && "content-disposition".equalsIgnoreCase(line.substring(0, colon).trim())) {
                return line.substring(colon + 1).trim();
            }
        }
        return "";
    }

    private static int skipLineBreak(final byte[] body, final int pos) {
        int next = pos;
        if (next < body.length && body[next] == '\r') {
            next += 1;
        }
        if (next < body.length && body[next] == '\n') {
            next += 1;
        }
        return next;
    }

    private static int find(final byte[] array, final byte[] target, final int from) {
        outer:
        for (int i = Math.max(from, 0); i <= array.length - target.length; i++) {
            for (int j = 0; j < target.length; j++) {
                if (array[i + j] != target[j]) {
                    continue outer;
                }
            }
            return i;
        }
        return -1;
    }

    private static long length(final RqHeaders.Smart headers) throws IOException {
        final String header = headers.single("Content-Length", "");
        if (header.isEmpty()) {
            throw new RejectedRequest(411, "В запросе нет заголовка Content-Length");
        }
        try {
            return Long.parseLong(header.trim());
        } catch (final NumberFormatException err) {
            throw new RejectedRequest(400, "Неверный заголовок Content-Length");
        }
    }
}
