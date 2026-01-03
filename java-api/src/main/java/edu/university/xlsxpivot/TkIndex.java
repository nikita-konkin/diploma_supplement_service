package edu.university.xlsxpivot;

import org.takes.Request;
import org.takes.Response;
import org.takes.Take;
import org.takes.rs.RsWithBody;
import org.takes.rs.RsWithStatus;
import org.takes.rs.RsWithType;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;

/**
 * Take that serves the `public/index.html` resource from the classpath.
 */
public final class TkIndex implements Take {

    @Override
    public Response act(final Request req) throws Exception {
        final InputStream in = this.getClass().getResourceAsStream("/public/index.html");
        if (in == null) {
            return new RsWithStatus(new RsWithBody("Not found"), 404);
        }
        final ByteArrayOutputStream buf = new ByteArrayOutputStream();
        final byte[] tmp = new byte[8192];
        int r;
        while ((r = in.read(tmp)) != -1) {
            buf.write(tmp, 0, r);
        }
        in.close();
        return new RsWithType(new RsWithBody(buf.toByteArray()), "text/html; charset=UTF-8");
    }
}
