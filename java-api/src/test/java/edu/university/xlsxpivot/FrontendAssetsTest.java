package edu.university.xlsxpivot;

import org.junit.Test;
import org.takes.rq.RqFake;
import org.takes.rs.RsPrint;

import static org.hamcrest.CoreMatchers.allOf;
import static org.hamcrest.CoreMatchers.containsString;
import static org.junit.Assert.assertThat;

public final class FrontendAssetsTest {

    @Test
    public void cannotServeStaleErrorParser() throws Exception {
        assertThat(
            "Browser received a cacheable or obsolete error parser",
            new RsPrint(new TkScript().act(new RqFake())).print(),
            allOf(
                containsString("Cache-Control: no-store, max-age=0"),
                containsString("JSON.parse(body)"),
                containsString("status.textContent = message")
            )
        );
    }

    @Test
    public void cannotReuseUnversionedScript() throws Exception {
        assertThat(
            "Page referenced an unversioned browser bundle",
            new RsPrint(new TkIndex().act(new RqFake())).print(),
            allOf(
                containsString("Cache-Control: no-store, max-age=0"),
                containsString("/script.js?v=error-contract-v2")
            )
        );
    }
}
