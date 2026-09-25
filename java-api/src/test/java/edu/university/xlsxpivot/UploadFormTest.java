package edu.university.xlsxpivot;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.concurrent.atomic.AtomicReference;
import org.junit.Test;
import org.takes.Request;
import org.takes.rq.RqFake;
import org.takes.rq.RqLengthAware;
import org.takes.rq.RqPrint;
import org.takes.http.FtRemote;
import org.takes.rs.RsPrint;
import org.takes.rs.RsText;

import static org.hamcrest.CoreMatchers.allOf;
import static org.hamcrest.CoreMatchers.containsString;
import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.assertThat;

public final class UploadFormTest {

    private static final byte[] WORKBOOK = {
        'P', 'K', 3, 4, 0, (byte) 0xFF, '\r', '\n', '-', '-', 'x', (byte) 0xD0, '\n', 0,
    };

    @Test
    public void cannotChangeBytesOfUploadedWorkbook() throws Exception {
        assertThat(
            "Uploaded workbook bytes changed on the way through the gateway",
            Arrays.equals(
                new UploadForm(UploadFormTest.request(), 1024)
                    .file("scores_xlsx", "ведомость")
                    .content(),
                UploadFormTest.WORKBOOK
            ),
            is(true)
        );
    }

    @Test
    public void cannotRejectFileWithCyrillicName() throws Exception {
        assertThat(
            "A workbook named in Russian was not recognised",
            new UploadForm(UploadFormTest.request(), 1024)
                .file("scores_xlsx", "ведомость")
                .name(),
            is("Оценки.xlsx")
        );
    }

    @Test
    public void cannotGarbleCyrillicFormField() throws Exception {
        assertThat(
            "A Cyrillic form field arrived garbled",
            new UploadForm(UploadFormTest.request(), 1024).params().get("profile"),
            is("Интеллектуальные информационные системы и технологии")
        );
    }

    @Test
    public void cannotReadBodyOfOversizedUpload() throws Exception {
        final Request huge = new Request() {
            @Override
            public Iterable<String> head() {
                return Arrays.asList(
                    "POST /pivot HTTP/1.1",
                    "Content-Type: multipart/form-data; boundary=b",
                    "Content-Length: 104857600"
                );
            }

            @Override
            public InputStream body() throws IOException {
                throw new IOException("the gateway started reading an oversized body");
            }
        };
        assertThat(
            "An oversized upload was read into memory instead of being refused",
            new RsPrint(new TkPivot((scores, disciplines, curriculum) -> new byte[0], 1024).act(huge)).print(),
            containsString("HTTP/1.1 413")
        );
    }

    @Test
    public void cannotHideWhichFileIsMissing() throws Exception {
        assertThat(
            "The user was not told which file is missing",
            new RsPrint(
                new TkPivot((scores, disciplines, curriculum) -> new byte[0], 1024)
                    .act(UploadFormTest.request())
            ).print(),
            allOf(
                containsString("HTTP/1.1 400"),
                containsString("Не выбран файл: список дисциплин учебного плана")
            )
        );
    }

    @Test
    public void cannotDropResponseAfterReadingUpload() throws Exception {
        final AtomicReference<Integer> status = new AtomicReference<>(0);
        new FtRemote(
            new TkPivot((scores, disciplines, curriculum) -> new byte[] {'P', 'K'}, 1024)
        ).exec(
            home -> {
                final Request req = UploadFormTest.request("disciplines_xlsx");
                final HttpURLConnection conn =
                    (HttpURLConnection) home.resolve("/pivot").toURL().openConnection();
                conn.setRequestMethod("POST");
                conn.setDoOutput(true);
                conn.setRequestProperty(
                    "Content-Type",
                    "multipart/form-data; boundary=angry-upload-boundary"
                );
                try (OutputStream out = conn.getOutputStream()) {
                    req.body().transferTo(out);
                }
                status.set(conn.getResponseCode());
            }
        );
        assertThat(
            "The gateway read the upload and closed the connection without an answer",
            status.get(),
            is(200)
        );
    }

    @Test
    public void cannotForwardOldExcelFileAsXlsx() throws Exception {
        final AtomicReference<String> received = new AtomicReference<>("");
        new FtRemote(
            req -> {
                received.set(new RqPrint(new RqLengthAware(req)).print());
                return new RsText("ok");
            }
        ).exec(
            home -> new PyEngineClient(home.toString().replaceAll("/$", "")).processPivot(
                new Upload("Оценки.xls", UploadFormTest.WORKBOOK),
                new Upload("План.xlsx", UploadFormTest.WORKBOOK),
                null
            )
        );
        assertThat(
            "An .xls workbook was forwarded under an .xlsx name",
            received.get(),
            containsString("filename=\"scores_xlsx.xls\"")
        );
    }

    @Test
    public void cannotDropUploadedCurriculum() throws Exception {
        final AtomicReference<String> received = new AtomicReference<>("");
        new FtRemote(
            req -> {
                received.set(new RqPrint(new RqLengthAware(req)).print());
                return new RsText("ok");
            }
        ).exec(
            home -> new PyEngineClient(home.toString().replaceAll("/$", "")).processPivot(
                new Upload("Оценки.xlsx", UploadFormTest.WORKBOOK),
                new Upload("Дисциплины.xlsx", UploadFormTest.WORKBOOK),
                new Upload("План.xlsx", UploadFormTest.WORKBOOK)
            )
        );
        assertThat(
            "The curriculum was not forwarded to the pivot service",
            received.get(),
            containsString("name=\"curriculum_xlsx\"")
        );
    }

    private static Request request() throws IOException {
        return UploadFormTest.request("profile");
    }

    private static Request request(final String second) throws IOException {
        final String boundary = "angry-upload-boundary";
        final ByteArrayOutputStream body = new ByteArrayOutputStream();
        body.write((
            "--" + boundary + "\r\n"
                + "Content-Disposition: form-data; name=\"scores_xlsx\"; filename=\"Оценки.xlsx\"\r\n"
                + "Content-Type: application/octet-stream\r\n\r\n"
        ).getBytes(StandardCharsets.UTF_8));
        body.write(UploadFormTest.WORKBOOK);
        body.write((
            "\r\n--" + boundary + "\r\n"
                + "Content-Disposition: form-data; name=\"" + second + "\""
                + (second.endsWith("xlsx") ? "; filename=\"План.xlsx\"" : "") + "\r\n\r\n"
                + "Интеллектуальные информационные системы и технологии\r\n"
                + "--" + boundary + "--\r\n"
        ).getBytes(StandardCharsets.UTF_8));
        return new RqFake(
            Arrays.asList(
                "POST /pivot HTTP/1.1",
                "Content-Type: multipart/form-data; boundary=" + boundary,
                "Content-Length: " + body.size()
            ),
            body.toByteArray()
        );
    }
}
